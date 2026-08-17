from functools import wraps

from flask import abort, session

ROLLEN = ("standard", "erweitert", "admin")


def require_erweitert(view):
    """Blockt die Rolle 'standard' von Betriebswechsel-/Betriebs-Bearbeiten-Routen.

    abort(403) statt Redirect: Standard-Benutzer sehen ohnehin keinen Link zu
    diesen Routen, ein direkter Zugriffsversuch ist also kein normaler
    Navigationsfehler, sondern soll klar abgewiesen werden.
    """

    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("rolle") == "standard":
            abort(403)
        return view(*args, **kwargs)

    return wrapped
