import os
from datetime import timedelta


def load_config():
    return {
        "DATABASE_URL": os.environ["DATABASE_URL"],
        "APP_USERNAME": os.environ["APP_USERNAME"],
        "APP_PASSWORD_HASH": os.environ["APP_PASSWORD_HASH"],
        "SECRET_KEY": os.environ["SECRET_KEY"],
        "IMPORT_DIR": os.environ.get("IMPORT_DIR", "/app/import"),
        "IMPORT_SCAN_INTERVAL_SECONDS": int(os.environ.get("IMPORT_SCAN_INTERVAL_SECONDS", "300")),
        "MAX_IMPORT_FAILURES": int(os.environ.get("MAX_IMPORT_FAILURES", "3")),
        "PERMANENT_SESSION_LIFETIME": timedelta(hours=int(os.environ.get("SESSION_LIFETIME_HOURS", "8"))),
    }
