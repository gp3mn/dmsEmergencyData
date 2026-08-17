import threading

from flask import Flask, redirect, request, session, url_for

from . import config as config_module
from .auth import bp as auth_bp
from .routes.admin import bp as admin_bp
from .routes.auftrag import bp as auftrag_bp
from .routes.benutzer import bp as benutzer_bp
from .routes.betrieb import bp as betrieb_bp
from .routes.einlagerungen import bp as einlagerungen_bp
from .routes.ersatzfahrzeuge import bp as ersatzfahrzeuge_bp
from .routes.search import bp as search_bp
from .routes.teilebestand import bp as teilebestand_bp
from .scanner import start_scanner

_scanner_lock = threading.Lock()
_scanner_started = False

# Endpunkte, die ohne Login erreichbar sein muessen.
_PUBLIC_ENDPOINTS = {"auth.login", "static"}


def create_app():
    app = Flask(__name__)
    app.config.update(config_module.load_config())

    app.register_blueprint(auth_bp)
    app.register_blueprint(betrieb_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(auftrag_bp)
    app.register_blueprint(teilebestand_bp)
    app.register_blueprint(einlagerungen_bp)
    app.register_blueprint(ersatzfahrzeuge_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(benutzer_bp)

    @app.before_request
    def enforce_login():
        if request.endpoint is None or request.endpoint in _PUBLIC_ENDPOINTS:
            return None
        if not session.get("user"):
            return redirect(url_for("auth.login", next=request.path))
        return None

    global _scanner_started
    with _scanner_lock:
        if not _scanner_started:
            start_scanner(app)
            _scanner_started = True

    return app
