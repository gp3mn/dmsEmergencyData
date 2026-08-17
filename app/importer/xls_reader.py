import xlrd
from xlrd.xldate import xldate_as_datetime

# Zweistellige Format-Codes sind ein zuverlaessigerer Hinweis auf ein
# Datums-/Zeitformat als einzelne Buchstaben (die auch in normalen
# Zahlenformaten vorkommen koennen). Deckt sowohl englische (dd/mm/yy/hh)
# als auch deutsche Excel-Formatcodes (tt/jj) ab.
_DATE_FORMAT_TOKENS = ("dd", "mm", "yy", "hh", "tt", "jj")
_PLAUSIBLE_YEAR_RANGE = (1990, 2100)


def read_sheet(path):
    """Liest das erste Tabellenblatt einer .xls-Datei.

    Gibt (headers, rows) zurueck. headers ist die rohe Kopfzeile (Liste von
    Strings), rows ist eine Liste von Zeilen (Liste von Werten). Werte sind
    bereits so weit wie moeglich aufgeloest: echte Datumszellen und Zellen,
    deren Zahlenformat wie ein Datum aussieht, werden zu datetime, alles
    andere bleibt str/float/bool/None. Eine leere Datei (nur Kopfzeile oder
    komplett leer) liefert eine leere rows-Liste, das ist kein Fehler.
    """
    # formatting_info=True ist noetig, damit xlrd das Zahlenformat einer Zelle
    # (xf_index/format_map) liefert -- ohne diese Option ist xf_index immer
    # None und echte Datumszellen liessen sich nicht von reinen Zahlen
    # unterscheiden. Nur fuer klassisches BIFF/.xls unterstuetzt (hier immer
    # der Fall).
    book = xlrd.open_workbook(path, formatting_info=True)
    sheet = book.sheet_by_index(0)

    if sheet.nrows == 0:
        return [], []

    headers = [(str(v).strip() if v is not None else "") for v in sheet.row_values(0)]

    rows = []
    for r in range(1, sheet.nrows):
        rows.append([_cell_value(sheet.cell(r, c), book) for c in range(sheet.ncols)])

    return headers, rows


def _cell_value(cell, book):
    ctype = cell.ctype
    value = cell.value

    if ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
        return None

    if ctype == xlrd.XL_CELL_TEXT:
        text = value.strip()
        return text or None

    if ctype == xlrd.XL_CELL_BOOLEAN:
        return bool(value)

    if ctype == xlrd.XL_CELL_ERROR:
        return None

    if ctype == xlrd.XL_CELL_DATE:
        return _safe_xldate(value, book.datemode)

    if ctype == xlrd.XL_CELL_NUMBER:
        if _format_looks_like_date(cell, book):
            resolved = _safe_xldate(value, book.datemode)
            if resolved is not None:
                return resolved
        return value

    return value


def _safe_xldate(value, datemode):
    """Loest eine Excel-Datumszahl auf.

    Zellen mit reinem Uhrzeitanteil (z.B. eine ANNAHMEUHRZEIT-Spalte) haben
    denselben ctype wie echte Datumszellen, ihr Zahlenwert ist aber nur ein
    Bruchteil < 1 (Anteil des Tages) ohne sinnvollen Datumsanteil -- xlrd
    wuerde das auf das Excel-Epoch-Datum (~1899) abbilden. Fuer solche Werte
    wird nur die Uhrzeit (datetime.time) zurueckgegeben; fuer echte Datumswerte
    wird die volle datetime zurueckgegeben, aber nur wenn das Jahr plausibel
    ist (schuetzt vor Fehlklassifizierung anderer Zahlen als Datum).
    """
    try:
        dt = xldate_as_datetime(value, datemode)
    except (xlrd.xldate.XLDateError, ValueError, OverflowError):
        return None
    if 0 <= value < 1:
        return dt.time()
    if not (_PLAUSIBLE_YEAR_RANGE[0] <= dt.year <= _PLAUSIBLE_YEAR_RANGE[1]):
        return None
    return dt


def _format_looks_like_date(cell, book):
    if cell.xf_index is None:
        return False
    try:
        xf = book.xf_list[cell.xf_index]
        fmt = book.format_map.get(xf.format_key)
    except (IndexError, AttributeError, TypeError):
        return False
    if fmt is None:
        return False
    format_str = fmt.format_str.lower()
    if "general" in format_str:
        return False
    return any(token in format_str for token in _DATE_FORMAT_TOKENS)
