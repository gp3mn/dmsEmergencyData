import psycopg2
import psycopg2.extras
from flask import current_app


def get_connection():
    return psycopg2.connect(current_app.config["DATABASE_URL"])


def dict_cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
