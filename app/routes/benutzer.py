from flask import Blueprint, abort, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from .. import db

ROLLEN = ("standard", "erweitert", "admin")

bp = Blueprint("benutzer", __name__, url_prefix="/admin/benutzer")


@bp.before_request
def _nur_admin():
    if session.get("rolle") != "admin":
        abort(403)


@bp.route("")
def liste():
    conn = db.get_connection()
    try:
        with db.dict_cursor(conn) as cur:
            cur.execute(
                "SELECT id, benutzername, rolle, betrieb, erstellt_am FROM benutzer ORDER BY benutzername"
            )
            benutzer = cur.fetchall()
    finally:
        conn.close()
    return render_template("benutzer_liste.html", benutzer=benutzer)


@bp.route("/neu", methods=["GET", "POST"])
def neu():
    error = None
    if request.method == "POST":
        benutzername = request.form.get("benutzername", "").strip()
        passwort = request.form.get("passwort", "")
        rolle = request.form.get("rolle", "")
        betrieb = request.form.get("betrieb", "").strip() or None

        if not benutzername:
            error = "Benutzername darf nicht leer sein."
        elif not passwort:
            error = "Passwort darf nicht leer sein."
        elif rolle not in ROLLEN:
            error = "Ungueltige Rolle."
        elif rolle == "standard" and not betrieb:
            error = "Bei Rolle 'Standard' muss ein Betrieb angegeben werden."

        if error is None:
            conn = db.get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM benutzer WHERE benutzername = %s", (benutzername,))
                    if cur.fetchone() is not None:
                        error = "Dieser Benutzername ist bereits vergeben."
                    else:
                        cur.execute(
                            """INSERT INTO benutzer (benutzername, passwort_hash, rolle, betrieb)
                               VALUES (%s, %s, %s, %s)""",
                            (
                                benutzername,
                                generate_password_hash(passwort),
                                rolle,
                                betrieb if rolle == "standard" else None,
                            ),
                        )
                        conn.commit()
            finally:
                conn.close()

            if error is None:
                return redirect(url_for("benutzer.liste"))

    betriebe = _betriebe_liste()
    return render_template("benutzer_neu.html", error=error, form=request.form, betriebe=betriebe)


@bp.route("/<int:benutzer_id>/loeschen", methods=["POST"])
def loeschen(benutzer_id):
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM benutzer WHERE id = %s", (benutzer_id,))
        conn.commit()
    finally:
        conn.close()
    return redirect(url_for("benutzer.liste"))


@bp.route("/<int:benutzer_id>/passwort", methods=["GET", "POST"])
def passwort(benutzer_id):
    conn = db.get_connection()
    try:
        if request.method == "POST":
            neues_passwort = request.form.get("passwort", "")
            if not neues_passwort:
                error = "Passwort darf nicht leer sein."
            else:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE benutzer SET passwort_hash = %s WHERE id = %s",
                        (generate_password_hash(neues_passwort), benutzer_id),
                    )
                    if cur.rowcount == 0:
                        abort(404)
                conn.commit()
                return redirect(url_for("benutzer.liste"))
        else:
            error = None

        with db.dict_cursor(conn) as cur:
            cur.execute("SELECT id, benutzername FROM benutzer WHERE id = %s", (benutzer_id,))
            zielbenutzer = cur.fetchone()
    finally:
        conn.close()

    if zielbenutzer is None:
        abort(404)
    return render_template("benutzer_passwort.html", error=error, zielbenutzer=zielbenutzer)


def _betriebe_liste():
    conn = db.get_connection()
    try:
        with db.dict_cursor(conn) as cur:
            cur.execute("SELECT betriebsnummer, firmenname FROM betriebe ORDER BY betriebsnummer")
            return cur.fetchall()
    finally:
        conn.close()
