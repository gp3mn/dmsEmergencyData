from flask import Blueprint, render_template, request, session

from .. import db
from ..betrieb_context import require_betrieb

bp = Blueprint("ersatzfahrzeuge", __name__)


@bp.route("/ersatzfahrzeuge")
@require_betrieb
def suche():
    betrieb = session["betrieb"]
    q = request.args.get("q", "").strip()

    conditions = ["f.betrieb = %s"]
    params = [betrieb]
    if q:
        conditions.append(
            "(f.mobilitaetbez ILIKE %s OR f.fzgkennung ILIKE %s OR f.amtlkz ILIKE %s "
            "OR f.auftragsnr ILIKE %s)"
        )
        params.extend([f"%{q}%"] * 4)

    sql = (
        "SELECT f.*, (a.auftragsnr IS NOT NULL) AS auftrag_vorhanden "
        "FROM ersatzfzgbelegung f "
        "LEFT JOIN auftraege a ON a.betrieb = f.betrieb AND a.auftragsnr = f.auftragsnr "
        "WHERE " + " AND ".join(conditions) +
        " ORDER BY f.gueltigab DESC NULLS LAST LIMIT 300"
    )

    conn = db.get_connection()
    try:
        with db.dict_cursor(conn) as cur:
            cur.execute(sql, params)
            results = cur.fetchall()
    finally:
        conn.close()

    return render_template("ersatzfahrzeuge.html", results=results, q=q)
