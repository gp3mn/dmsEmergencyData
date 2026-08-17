import glob
import logging
import os
import shutil
import tempfile
import zipfile

from psycopg2.extras import Json, execute_values

from . import schema, xls_reader

logger = logging.getLogger(__name__)


def import_one(conn, betrieb, zip_path):
    """Importiert eine ZIP-Datei fuer genau einen Betrieb.

    Parst zuerst alle 5 Dateien vollstaendig in Python-Strukturen; erst wenn
    das ohne Fehler gelingt, wird in der uebergebenen (bereits offenen)
    Transaktion je Tabelle "DELETE ... WHERE betrieb=..." gefolgt von einem
    Bulk-Insert ausgefuehrt. Committet wird NICHT hier -- das macht der
    Aufrufer, zusammen mit dem Update des import_log-Eintrags, damit
    Datenaustausch und Protokollierung atomar zusammen durchgesetzt werden.
    Bei einer Exception (Parsing- oder DB-Fehler) bleiben die Daten des
    Betriebs unveraendert, wenn der Aufrufer die Transaktion zurueckrollt.
    """
    tmp_dir = tempfile.mkdtemp(prefix="notfall_import_")
    try:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp_dir)

        parsed = {}
        for table_key, spec in schema.TABLES.items():
            file_path = _find_file(tmp_dir, spec["file_suffix"])
            headers, rows = xls_reader.read_sheet(file_path)
            built = schema.build_rows(table_key, headers, rows) if headers else []
            if table_key == "auftraege":
                built = _dedupe_auftraege(built, betrieb)
            parsed[table_key] = built

        counts = {}
        with conn.cursor() as cur:
            for table_key in schema.TABLES:
                cur.execute(f"DELETE FROM {table_key} WHERE betrieb = %s", (betrieb,))
            for table_key, rows in parsed.items():
                counts[table_key] = _insert_rows(cur, table_key, betrieb, rows)
        return counts
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _dedupe_auftraege(rows, betrieb):
    """Das Quellsystem liefert manchmal mehrere fast identische Zeilen fuer
    dieselbe AUFTRAGSNR (offenbar je Kombination aus Abhol-/Zustelltermin) --
    auftraege hat aber (betrieb, auftragsnr) als Primaerschluessel, da die
    Detailseite genau eine Kopfzeile pro Auftrag erwartet. Die letzte Zeile
    je AUFTRAGSNR gewinnt; das ist als reine Nachschlage-Referenz fuer den
    Notfall ausreichend, ein Datenverlust bei einer einzelnen Logistik-
    Kombination ist hier vertretbar.
    """
    deduped = {}
    for row in rows:
        deduped[row.get("auftragsnr")] = row
    if len(deduped) != len(rows):
        logger.warning(
            "Betrieb %s: %d doppelte AUFTRAGSNR-Zeilen in auftragskopf zusammengefuehrt (%d -> %d Zeilen)",
            betrieb, len(rows) - len(deduped), len(rows), len(deduped),
        )
    return list(deduped.values())


def _find_file(tmp_dir, suffix):
    matches = glob.glob(os.path.join(tmp_dir, f"*.{suffix}.xls"))
    if not matches:
        raise FileNotFoundError(f"Keine Datei mit Endung '.{suffix}.xls' im ZIP gefunden")
    if len(matches) > 1:
        raise ValueError(f"Mehrere Dateien fuer '{suffix}' im ZIP gefunden: {matches}")
    return matches[0]


def _insert_rows(cur, table_key, betrieb, rows):
    if not rows:
        return 0
    db_columns = [db_col for _, db_col, _ in schema.TABLES[table_key]["columns"]]
    all_columns = ["betrieb"] + db_columns + ["raw_row"]
    values = [
        tuple([betrieb] + [row.get(col) for col in db_columns] + [Json(row.get("raw_row"))])
        for row in rows
    ]
    columns_sql = ", ".join(all_columns)
    execute_values(cur, f"INSERT INTO {table_key} ({columns_sql}) VALUES %s", values, page_size=500)
    return len(values)
