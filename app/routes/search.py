from flask import Blueprint, render_template, request, session

from .. import db
from ..betrieb_context import require_betrieb

bp = Blueprint("search", __name__)


@bp.route("/suche")
@require_betrieb
def suche():
    betrieb = session["betrieb"]
    form = {
        "auftragsnr": request.args.get("auftragsnr", "").strip(),
        "kundenname": request.args.get("kundenname", "").strip(),
        "amtlkz": request.args.get("amtlkz", "").strip(),
        "fgstnr": request.args.get("fgstnr", "").strip(),
        "von": request.args.get("von", "").strip(),
        "bis": request.args.get("bis", "").strip(),
    }
    hat_suche = any(form.values())

    results = []
    if hat_suche:
        conditions = ["betrieb = %s"]
        params = [betrieb]
        if form["auftragsnr"]:
            conditions.append("auftragsnr ILIKE %s")
            params.append(f"%{form['auftragsnr']}%")
        if form["kundenname"]:
            conditions.append("kundenname ILIKE %s")
            params.append(f"%{form['kundenname']}%")
        if form["amtlkz"]:
            conditions.append("amtlkz ILIKE %s")
            params.append(f"%{form['amtlkz']}%")
        if form["fgstnr"]:
            conditions.append("fgstnr ILIKE %s")
            params.append(f"%{form['fgstnr']}%")
        if form["von"]:
            conditions.append("annahmedatum >= %s")
            params.append(form["von"])
        if form["bis"]:
            conditions.append("annahmedatum <= %s")
            params.append(form["bis"])

        sql = (
            "SELECT auftragsnr, kundenname, amtlkz, fahrzeugmodell, annahmedatum "
            "FROM auftraege WHERE " + " AND ".join(conditions) +
            " ORDER BY annahmedatum DESC NULLS LAST, auftragsnr DESC LIMIT 200"
        )
        conn = db.get_connection()
        try:
            with db.dict_cursor(conn) as cur:
                cur.execute(sql, params)
                results = cur.fetchall()
        finally:
            conn.close()

    conn = db.get_connection()
    try:
        with db.dict_cursor(conn) as cur:
            cur.execute(
                "SELECT betriebsnummer, name, letzter_datenstand, letzter_import_at, letzter_status "
                "FROM betriebe WHERE betriebsnummer = %s",
                (betrieb,),
            )
            betrieb_info = cur.fetchone()
    finally:
        conn.close()

    return render_template(
        "search.html",
        results=results,
        hat_suche=hat_suche,
        form=form,
        betrieb_info=betrieb_info,
    )
