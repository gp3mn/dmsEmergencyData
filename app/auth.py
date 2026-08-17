from flask import Blueprint, current_app, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from . import db

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        expected_hash = current_app.config["APP_PASSWORD_HASH"]
        if username == current_app.config["APP_USERNAME"] and check_password_hash(expected_hash, password):
            # ENV-Fallback-Zugang: wirkt immer als Admin, ohne Betriebsbindung.
            # Bleibt dauerhaft bestehen, damit man nie ausgesperrt werden kann,
            # selbst wenn die Benutzerverwaltung leer ist oder alle DB-Admin-
            # Konten geloescht wurden.
            session.clear()
            session.permanent = True
            session["user"] = username
            session["rolle"] = "admin"
            next_url = request.args.get("next") or url_for("betrieb.index")
            return redirect(next_url)

        benutzer = _finde_benutzer(username)
        if benutzer and check_password_hash(benutzer["passwort_hash"], password):
            session.clear()
            session.permanent = True
            session["user"] = benutzer["benutzername"]
            session["rolle"] = benutzer["rolle"]
            session["benutzer_id"] = benutzer["id"]
            if benutzer["rolle"] == "standard":
                # Bewusst direkt zu /suche, nicht ueber next/betrieb.index --
                # ein Standard-Benutzer soll die Betriebsauswahl nie sehen,
                # auch nicht ueber einen praeparierten ?next=.
                session["betrieb"] = benutzer["betrieb"]
                return redirect(url_for("search.suche"))
            next_url = request.args.get("next") or url_for("betrieb.index")
            return redirect(next_url)

        error = "Benutzername oder Passwort ist falsch."
    return render_template("login.html", error=error)


def _finde_benutzer(username):
    conn = db.get_connection()
    try:
        with db.dict_cursor(conn) as cur:
            cur.execute(
                "SELECT id, benutzername, passwort_hash, rolle, betrieb FROM benutzer WHERE benutzername = %s",
                (username,),
            )
            return cur.fetchone()
    finally:
        conn.close()


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
