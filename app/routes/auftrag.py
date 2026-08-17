from flask import Blueprint, abort, render_template, session

from .. import db
from ..betrieb_context import require_betrieb

bp = Blueprint("auftrag", __name__)


def _kombiniere_beschreibung(bezeichnung, freiertext):
    """BEZEICHNUNG ist im Export oft laengenbegrenzt/abgeschnitten, FREIERTEXT
    enthaelt dann denselben Text vollstaendig -- ohne diese Zusammenfuehrung
    wuerde der Ausdruck denselben Satz zweimal (einmal abgeschnitten) zeigen.
    """
    bez = (bezeichnung or "").strip()
    frei = (freiertext or "").strip()
    if not frei or frei == bez:
        return bez
    if not bez or frei.startswith(bez) or bez.startswith(frei):
        return frei if len(frei) >= len(bez) else bez
    return f"{bez}\n{frei}"


def _load_auftrag(betrieb, auftragsnr):
    conn = db.get_connection()
    try:
        with db.dict_cursor(conn) as cur:
            cur.execute(
                "SELECT * FROM auftraege WHERE betrieb = %s AND auftragsnr = %s",
                (betrieb, auftragsnr),
            )
            kopf = cur.fetchone()
            if kopf is None:
                return None

            cur.execute(
                "SELECT * FROM auftragspositionen WHERE betrieb = %s AND auftragsnr = %s ORDER BY id",
                (betrieb, auftragsnr),
            )
            positionen = cur.fetchall()
            for p in positionen:
                p["beschreibung_anzeige"] = _kombiniere_beschreibung(p["bezeichnung"], p["freiertext"])

            cur.execute(
                "SELECT * FROM einlagerungen WHERE betrieb = %s AND auftragsnr = %s",
                (betrieb, auftragsnr),
            )
            einlagerungen = cur.fetchall()

            cur.execute(
                "SELECT * FROM ersatzfzgbelegung WHERE betrieb = %s AND auftragsnr = %s",
                (betrieb, auftragsnr),
            )
            ersatzfzg = cur.fetchall()

            cur.execute(
                "SELECT firmenname, name, strasse, plz_ort, telefon FROM betriebe WHERE betriebsnummer = %s",
                (betrieb,),
            )
            standort = cur.fetchone()
    finally:
        conn.close()

    return {
        "kopf": kopf,
        "positionen": positionen,
        "einlagerungen": einlagerungen,
        "ersatzfzg": ersatzfzg,
        "standort": standort,
    }


@bp.route("/auftrag/<auftragsnr>")
@require_betrieb
def detail(auftragsnr):
    data = _load_auftrag(session["betrieb"], auftragsnr)
    if data is None:
        abort(404)
    return render_template("auftrag_detail.html", **data)


@bp.route("/auftrag/<auftragsnr>/druck")
@require_betrieb
def druck(auftragsnr):
    data = _load_auftrag(session["betrieb"], auftragsnr)
    if data is None:
        abort(404)
    return render_template("auftrag_print.html", **data)
