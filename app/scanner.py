import glob
import logging
import os
import re
import threading
import time
from datetime import datetime

from flask import current_app

from . import db
from .importer import run_import

logger = logging.getLogger(__name__)

# 20260817000745_notfall.48755.zip -> Datenstand 2026-08-17, Betrieb 48755.
FILENAME_RE = re.compile(r"^(\d{8})(\d{6})_notfall\.(\d+)\.zip$")


def parse_filename(filename):
    match = FILENAME_RE.match(filename)
    if not match:
        return None
    datenstand_str, _zeit_str, betrieb = match.groups()
    try:
        datenstand = datetime.strptime(datenstand_str, "%Y%m%d").date()
    except ValueError:
        return None
    return {"betrieb": betrieb, "datenstand": datenstand}


def start_scanner(app):
    """Startet den Hintergrund-Scan als Daemon-Thread. Wird von create_app()
    genau einmal aufgerufen (Guard dort). Ein einzelner gunicorn-Worker
    (--workers 1) sorgt dafuer, dass nie mehrere Scanner-Threads gleichzeitig
    laufen; der pg_try_advisory_lock je Betrieb in scan_once() ist zusaetzlich
    eine guenstige Absicherung gegen Race Conditions mit dem manuellen
    "Jetzt importieren"-Button.
    """
    interval = app.config["IMPORT_SCAN_INTERVAL_SECONDS"]

    def loop():
        with app.app_context():
            while True:
                try:
                    scan_once()
                except Exception:
                    logger.exception("Scan-Durchlauf fehlgeschlagen")
                time.sleep(interval)

    thread = threading.Thread(target=loop, name="import-scanner", daemon=True)
    thread.start()


def scan_once(triggered_by="scanner"):
    import_dir = current_app.config["IMPORT_DIR"]
    processed_dir = os.path.join(import_dir, "processed")
    os.makedirs(processed_dir, exist_ok=True)

    zip_paths = sorted(glob.glob(os.path.join(import_dir, "*.zip")))

    parsed_by_path = {}
    for path in zip_paths:
        filename = os.path.basename(path)
        parsed = parse_filename(filename)
        if parsed is None:
            logger.warning("Ignoriere Datei mit unerwartetem Namen: %s", filename)
            continue
        parsed_by_path[path] = parsed

    # Je Betrieb nur die neueste Datei importieren -- aeltere ausstehende
    # Dateien desselben Betriebs sind durch den naechsten Import ohnehin
    # hinfaellig (kein Verlauf, jeder Import ist ein Vollersatz).
    newest_by_betrieb = {}
    for path, parsed in parsed_by_path.items():
        betrieb = parsed["betrieb"]
        filename = os.path.basename(path)
        current_best = newest_by_betrieb.get(betrieb)
        if current_best is None or filename > os.path.basename(current_best["path"]):
            newest_by_betrieb[betrieb] = {"path": path, "filename": filename, **parsed}

    for path, parsed in parsed_by_path.items():
        winner = newest_by_betrieb.get(parsed["betrieb"])
        if winner and winner["path"] != path:
            _mark_superseded(os.path.basename(path), parsed["betrieb"], parsed["datenstand"])
            _archive(path, processed_dir)

    for info in newest_by_betrieb.values():
        _import_one_betrieb(info, processed_dir, triggered_by)


def _already_handled(filename):
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM import_log WHERE zip_filename = %s "
                "AND status IN ('success', 'running', 'skipped_superseded') LIMIT 1",
                (filename,),
            )
            return cur.fetchone() is not None
    finally:
        conn.close()


def _mark_superseded(filename, betrieb, datenstand):
    if _already_handled(filename):
        return
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO import_log (betrieb, zip_filename, datenstand, status, finished_at, triggered_by)
                   VALUES (%s, %s, %s, 'skipped_superseded', now(), 'scanner')""",
                (betrieb, filename, datenstand),
            )
        conn.commit()
    finally:
        conn.close()


def _archive(path, processed_dir):
    target = os.path.join(processed_dir, os.path.basename(path))
    try:
        os.replace(path, target)
    except OSError:
        logger.exception("Konnte %s nicht nach processed/ verschieben", path)


def _import_one_betrieb(info, processed_dir, triggered_by):
    filename, betrieb, path, datenstand = info["filename"], info["betrieb"], info["path"], info["datenstand"]

    if _already_handled(filename):
        return

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(hashtext(%s))", (f"import:{betrieb}",))
            got_lock = cur.fetchone()[0]
        if not got_lock:
            logger.info("Import fuer Betrieb %s laeuft bereits, ueberspringe diesen Tick", betrieb)
            return

        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO import_log (betrieb, zip_filename, datenstand, status, triggered_by)
                   VALUES (%s, %s, %s, 'running', %s) RETURNING id""",
                (betrieb, filename, datenstand, triggered_by),
            )
            log_id = cur.fetchone()[0]
        conn.commit()

        try:
            counts = run_import.import_one(conn, betrieb, path)
        except Exception as exc:
            conn.rollback()
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE import_log SET status='failed', finished_at=now(), error_message=%s WHERE id=%s",
                    (str(exc)[:2000], log_id),
                )
                cur.execute(
                    "SELECT count(*) FROM import_log WHERE zip_filename = %s AND status = 'failed'",
                    (filename,),
                )
                failure_count = cur.fetchone()[0]
            conn.commit()
            logger.exception("Import fuer Betrieb %s (%s) fehlgeschlagen", betrieb, filename)

            max_failures = current_app.config["MAX_IMPORT_FAILURES"]
            if failure_count >= max_failures:
                # Nach wiederholten Fehlversuchen derselben Datei nicht mehr
                # automatisch erneut probieren (sonst wird jeder Scan-Tick
                # denselben Fehler erneut loggen) -- Datei bleibt fuer eine
                # manuelle Pruefung sichtbar, statt in processed/ zu verschwinden.
                quarantine_path = path + ".failed"
                try:
                    os.replace(path, quarantine_path)
                    logger.error(
                        "Betrieb %s: %s nach %s Fehlversuchen als .failed markiert, kein weiterer Retry",
                        betrieb, filename, failure_count,
                    )
                except OSError:
                    logger.exception("Konnte %s nicht als .failed markieren", path)
            return

        with conn.cursor() as cur:
            cur.execute(
                """UPDATE import_log SET status='success', finished_at=now(),
                       rows_auftraege=%s, rows_auftragspositionen=%s, rows_einlagerungen=%s,
                       rows_ersatzfzgbelegung=%s, rows_teilebestand=%s
                   WHERE id=%s""",
                (
                    counts.get("auftraege", 0),
                    counts.get("auftragspositionen", 0),
                    counts.get("einlagerungen", 0),
                    counts.get("ersatzfzgbelegung", 0),
                    counts.get("teilebestand", 0),
                    log_id,
                ),
            )
            cur.execute(
                """INSERT INTO betriebe (betriebsnummer, letzter_datenstand, letzter_import_at, letzter_status)
                   VALUES (%s, %s, now(), 'success')
                   ON CONFLICT (betriebsnummer) DO UPDATE SET
                       letzter_datenstand = EXCLUDED.letzter_datenstand,
                       letzter_import_at = EXCLUDED.letzter_import_at,
                       letzter_status = EXCLUDED.letzter_status""",
                (betrieb, datenstand),
            )
        conn.commit()
        _archive(path, processed_dir)
        logger.info("Import fuer Betrieb %s (%s) erfolgreich: %s", betrieb, filename, counts)
    finally:
        conn.close()
