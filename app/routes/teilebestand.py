from flask import Blueprint, render_template, request, session

from .. import db
from ..betrieb_context import require_betrieb

bp = Blueprint("teilebestand", __name__)


@bp.route("/teilebestand")
@require_betrieb
def suche():
    betrieb = session["betrieb"]
    q = request.args.get("q", "").strip()
    alle_betriebe = request.args.get("alle_betriebe") == "1"

    results = []
    if q:
        conditions = ["(t.teilenummer ILIKE %s OR t.teilebezeichnung ILIKE %s)"]
        params = [f"%{q}%", f"%{q}%"]
        if not alle_betriebe:
            conditions.append("t.betrieb = %s")
            params.append(betrieb)

        sql = (
            "SELECT t.betrieb, b.name AS betrieb_name, t.teilenummer, t.teilebezeichnung, "
            "t.gesamtbestandsmenge, t.bestandneu, t.verkaufspreis, t.lagerortneu "
            "FROM teilebestand t LEFT JOIN betriebe b ON b.betriebsnummer = t.betrieb "
            "WHERE " + " AND ".join(conditions) +
            " ORDER BY t.teilebezeichnung LIMIT 200"
        )
        conn = db.get_connection()
        try:
            with db.dict_cursor(conn) as cur:
                cur.execute(sql, params)
                results = cur.fetchall()
        finally:
            conn.close()

    return render_template("teilebestand.html", results=results, q=q, alle_betriebe=alle_betriebe)
