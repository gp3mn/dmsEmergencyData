from flask import Blueprint, render_template, request, session

from .. import db
from ..betrieb_context import require_betrieb

bp = Blueprint("einlagerungen", __name__)


@bp.route("/einlagerungen")
@require_betrieb
def suche():
    betrieb = session["betrieb"]
    q = request.args.get("q", "").strip()

    conditions = ["e.betrieb = %s"]
    params = [betrieb]
    if q:
        conditions.append(
            "(e.kundenname1 ILIKE %s OR e.kundenname2 ILIKE %s OR e.amtlkz ILIKE %s "
            "OR e.auftragsnr ILIKE %s OR e.lagerort ILIKE %s OR e.depotnr ILIKE %s)"
        )
        params.extend([f"%{q}%"] * 6)

    sql = (
        "SELECT e.*, (a.auftragsnr IS NOT NULL) AS auftrag_vorhanden "
        "FROM einlagerungen e "
        "LEFT JOIN auftraege a ON a.betrieb = e.betrieb AND a.auftragsnr = e.auftragsnr "
        "WHERE " + " AND ".join(conditions) +
        " ORDER BY e.lagerort NULLS LAST, e.depotnr NULLS LAST LIMIT 300"
    )

    conn = db.get_connection()
    try:
        with db.dict_cursor(conn) as cur:
            cur.execute(sql, params)
            results = cur.fetchall()
    finally:
        conn.close()

    return render_template("einlagerungen.html", results=results, q=q)
