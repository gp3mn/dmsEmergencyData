import re
from datetime import datetime, time
from decimal import Decimal, InvalidOperation

_UMLAUT_MAP = {"Ä": "AE", "Ö": "OE", "Ü": "UE", "ß": "SS"}
_NON_ALNUM_RE = re.compile(r"[^A-Z0-9]")
# xlrd hat in diesem Export beobachtet einzelne Umlaute (z.B. in
# "MOBILITÄTSART", "RÜCKGABEART") als Unicode-Replacement-Character (U+FFFD)
# dekodiert statt als echten Umlaut -- vermutlich ein Codepage-Problem in der
# Quelldatei. Welcher Umlaut urspruenglich gemeint war, laesst sich aus einem
# blossen Replacement-Character nicht rekonstruieren.
_REPLACEMENT_CHAR = "�"


def _normalize_ascii(text):
    for umlaut, replacement in _UMLAUT_MAP.items():
        text = text.replace(umlaut, replacement)
    return _NON_ALNUM_RE.sub("", text)


def normalize_header(value):
    """Eindeutige Normalform fuer Spaltennamen: Gross/Klein, Umlaute (echt
    oder bereits als AE/OE/UE geschrieben) und Trennzeichen spielen dann keine
    Rolle mehr. Wird fuer unsere eigenen (fest hinterlegten) Spalten-Namen
    benutzt, die keine kaputten Umlaute enthalten.
    """
    if value is None:
        return ""
    return _normalize_ascii(str(value).strip().upper())


def normalize_header_variants(value):
    """Wie normalize_header(), liefert aber bei einem Replacement-Character
    mehrere Kandidaten-Normalformen (je eine pro moeglichem Umlaut). Damit
    laesst sich ein aus der Quelldatei gelesener Spaltenname gegen unsere
    eigene, garantiert saubere Normalform abgleichen, auch wenn der Original-
    Umlaut beim Dekodieren verloren gegangen ist.
    """
    if value is None:
        return {""}
    text = str(value).strip().upper()
    if _REPLACEMENT_CHAR not in text:
        return {_normalize_ascii(text)}
    return {_normalize_ascii(text.replace(_REPLACEMENT_CHAR, r)) for r in ("AE", "OE", "UE", "SS")}


def clean_text(value):
    if value is None:
        return None
    if isinstance(value, time):
        return value.strftime("%H:%M")
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    text = str(value).strip()
    return text or None


def coerce_auftragsnr(value):
    """AUFTRAGSNR kommt aus xlrd typischerweise als float (z.B. 48755.0), da
    reine Ziffernfolgen ohne fuehrende Nullen als numerische Zelle abgelegt
    werden. Ohne diese Vereinheitlichung wuerden Joins zwischen den 5 Tabellen
    an unterschiedlicher Typisierung (48755.0 vs. "48755") scheitern.
    """
    if value is None:
        return None
    if isinstance(value, float):
        if value == int(value):
            return str(int(value))
        return str(value)
    if isinstance(value, int):
        return str(value)
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text or None


_DECIMAL_CLEAN_RE = re.compile(r"[^0-9,.\-]")


def parse_decimal(value):
    """Deutsche Komma-Dezimalzahlen als Text (z.B. "248,6", "1.234,56")
    sowie bereits numerische Zellen werden zu Decimal konvertiert."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    text = _DECIMAL_CLEAN_RE.sub("", str(value).strip())
    if not text:
        return None
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


_DATETIME_FORMATS = (
    "%d-%m-%Y %H:%M",
    "%d.%m.%Y %H:%M",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
)


def parse_text_datetime(text):
    text = text.strip()
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def to_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        parsed = parse_text_datetime(value)
        return parsed.date() if parsed else None
    return None


def to_datetime(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return parse_text_datetime(value)
    return None
