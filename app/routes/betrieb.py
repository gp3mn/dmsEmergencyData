from flask import Blueprint, abort, redirect, render_template, request, session, url_for

from .. import db
from ..auth_context import require_erweitert

bp = Blueprint("betrieb", __name__)


@bp.route("/")
def index():
    if session.get("betrieb"):
        return redirect(url_for("search.suche"))
    return redirect(url_for("betrieb.auswahl"))


@bp.route("/betriebe")
@require_erweitert
def auswahl():
    conn = db.get_connection()
    try:
        with db.dict_cursor(conn) as cur:
            cur.execute(
                "SELECT betriebsnummer, firmenname, name, strasse, plz_ort, telefon, "
                "letzter_datenstand, letzter_import_at, letzter_status "
                "FROM betriebe ORDER BY betriebsnummer"
            )
            betriebe = cur.fetchall()
    finally:
        conn.close()
    return render_template("betrieb_auswahl.html", betriebe=betriebe)


@bp.route("/betrieb/<nr>/bearbeiten", methods=["GET", "POST"])
@require_erweitert
def bearbeiten(nr):
    conn = db.get_connection()
    try:
        if request.method == "POST":
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE betriebe SET firmenname = %s, name = %s, strasse = %s, plz_ort = %s, telefon = %s
                       WHERE betriebsnummer = %s""",
                    (
                        request.form.get("firmenname", "").strip() or None,
                        request.form.get("name", "").strip() or None,
                        request.form.get("strasse", "").strip() or None,
                        request.form.get("plz_ort", "").strip() or None,
                        request.form.get("telefon", "").strip() or None,
                        nr,
                    ),
                )
                if cur.rowcount == 0:
                    abort(404)
            conn.commit()
            return redirect(url_for("betrieb.auswahl"))

        with db.dict_cursor(conn) as cur:
            cur.execute("SELECT * FROM betriebe WHERE betriebsnummer = %s", (nr,))
            betrieb = cur.fetchone()
    finally:
        conn.close()

    if betrieb is None:
        abort(404)
    return render_template("betrieb_bearbeiten.html", betrieb=betrieb)


@bp.route("/betrieb/<nr>/waehlen", methods=["POST"])
@require_erweitert
def waehlen(nr):
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM betriebe WHERE betriebsnummer = %s", (nr,))
            exists = cur.fetchone() is not None
    finally:
        conn.close()
    if not exists:
        return redirect(url_for("betrieb.auswahl"))
    session["betrieb"] = nr
    return redirect(url_for("search.suche"))
