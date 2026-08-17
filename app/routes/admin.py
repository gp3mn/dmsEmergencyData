from flask import Blueprint, jsonify, render_template, session

from .. import db, scanner

bp = Blueprint("admin", __name__)


@bp.route("/import/jetzt", methods=["POST"])
def jetzt():
    user = session.get("user", "unbekannt")
    scanner.scan_once(triggered_by=f"manual:{user}")
    return jsonify({"status": "ok"})


@bp.route("/import/status")
def status():
    conn = db.get_connection()
    try:
        with db.dict_cursor(conn) as cur:
            cur.execute(
                "SELECT betrieb, zip_filename, datenstand, status, started_at, finished_at, "
                "error_message, triggered_by FROM import_log ORDER BY started_at DESC LIMIT 50"
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return render_template("import_status.html", rows=rows)
