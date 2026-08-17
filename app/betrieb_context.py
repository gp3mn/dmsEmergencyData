from functools import wraps

from flask import redirect, session, url_for


def require_betrieb(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("betrieb"):
            return redirect(url_for("betrieb.auswahl"))
        return view(*args, **kwargs)

    return wrapped
