"""Spalten-Mapping je Zieltabelle: (Quell-Header aus der .xls, DB-Spalte, Typ).

Der Quell-Header wird ueber convert.normalize_header() abgeglichen, daher
spielt Gross-/Kleinschreibung und die genaue Schreibweise von Umlauten keine
Rolle. file_suffix identifiziert die zugehoerige Datei im ZIP
(notfall.<betrieb>.<file_suffix>.xls).
"""

from datetime import datetime

from . import convert

TABLES = {
    "auftraege": {
        "file_suffix": "auftragskopf",
        "columns": [
            ("ANNAHMEDATUM", "annahmedatum", "date"),
            ("ANNAHMEUHRZEIT", "annahmeuhrzeit", "text"),
            ("ANNAHMEART", "annahmeart", "text"),
            ("ANNAHMESB", "annahmesb", "text"),
            ("AUFTRAGSTYP", "auftragstyp", "text"),
            ("KUNDENNAME", "kundenname", "text"),
            ("FAHRER", "fahrer", "text"),
            ("AMTLKZ", "amtlkz", "text"),
            ("FAHRZEUGMODELL", "fahrzeugmodell", "text"),
            ("AUFTRAGSNR", "auftragsnr", "auftragsnr"),
            ("ADRESSEKUNDE", "adressekunde", "text"),
            ("TELEFONNR1", "telefonnr1", "text"),
            ("TELEFONNR2", "telefonnr2", "text"),
            ("MARKE", "marke", "text"),
            ("FGSTNR", "fgstnr", "text"),
            ("ABHOLDATUM", "abholdatum", "date"),
            ("ABHOLUHRZEIT", "abholuhrzeit", "text"),
            ("ABHOLER", "abholer", "text"),
            ("ABHOLBEMERKUNG", "abholbemerkung", "text"),
            ("ANNAHMEBEMERKUNG", "annahmebemerkung", "text"),
            ("VERANTWORTLSB", "verantwortlsb", "text"),
            ("MOBILITAETSART", "mobilitaetsart", "text"),
            ("ERSATZFAHRZEUG", "ersatzfahrzeug", "text"),
            ("FERTIGSTELLUNGSDATUM", "fertigstellungsdatum", "date"),
            ("FERTIGSTELLUNGSUHRZEIT", "fertigstellungsuhrzeit", "text"),
            ("RUECKGABEART", "rueckgabeart", "text"),
            ("RUECKGABEDATUM", "rueckgabedatum", "date"),
            ("RUECKGABEUHRZEIT", "rueckgabeuhrzeit", "text"),
            ("RUECKGABESB", "rueckgabesb", "text"),
            ("RUECKGABEBEMERKUNG", "rueckgabebemerkung", "text"),
            ("ZUSTELLDATUM", "zustelldatum", "date"),
            ("ZUSTELLUHRZEIT", "zustelluhrzeit", "text"),
            ("ZUSTELLER", "zusteller", "text"),
            ("ZUSTELLBEMERKUNG", "zustellbemerkung", "text"),
            ("KUNDEBRUTTO", "kundebrutto", "decimal2"),
            ("RECHNUNGSSTATUS", "rechnungsstatus", "text"),
            ("KUNDEWARTET", "kundewartet", "text"),
            ("DURCHFSTATUS", "durchfstatus", "text"),
            ("WIEDERHOLREPARATUR", "wiederholreparatur", "text"),
            ("STEMPELUNG_DATUM", "stempelung_datum", "date"),
            ("STEMPELUNG_STARTZEIT", "stempelung_startzeit", "text"),
            ("STEMPELUNG_ENDZEIT", "stempelung_endzeit", "text"),
            ("STEMPELUNG_AUFTRAGFERTIG", "stempelung_auftragfertig", "text"),
            ("STEMPELUNG_ANMERKUNG", "stempelung_anmerkung", "text"),
            ("STEMPELUNG_MECHANIKERNR", "stempelung_mechanikernr", "text"),
            ("ARBEITSZEIT_GESAMT", "arbeitszeit_gesamt", "decimal2"),
            ("ARBEITSZEIT_GESTEMPELT", "arbeitszeit_gestempelt", "decimal2"),
        ],
    },
    "auftragspositionen": {
        "file_suffix": "auftragspositionen",
        "columns": [
            ("REPARATURDATUM", "reparaturdatum", "date"),
            ("ANNAHMESB", "annahmesb", "text"),
            ("VERANTWORTLSB", "verantwortlsb", "text"),
            ("AUFTRAGSNR", "auftragsnr", "auftragsnr"),
            ("SUBAUFTRAGSNR", "subauftragsnr", "text"),
            ("AUFTRAGSTYP", "auftragstyp", "text"),
            ("AUFTRAGSART", "auftragsart", "text"),
            ("POSITIONSKZ", "positionskz", "text"),
            ("IDENTIFIER", "identifier", "text"),
            ("BEZEICHNUNG", "bezeichnung", "text"),
            ("MENGE", "menge", "decimal3"),
            ("ZEITEINHEITEN", "zeiteinheiten", "decimal3"),
            ("FREIERTEXT", "freiertext", "text"),
            ("PLANUNGSGRPNR", "planungsgrpnr", "text"),
            ("PLANUNGSGRPBEZ", "planungsgrpbez", "text"),
        ],
    },
    "einlagerungen": {
        "file_suffix": "einlagerungen",
        "columns": [
            ("LAGERORT", "lagerort", "text"),
            ("DEPOTNR", "depotnr", "text"),
            ("STATUS", "status", "text"),
            ("EINLAGERUNG_AUFTRAGSNR", "auftragsnr", "auftragsnr"),
            ("KUNDENNAME1", "kundenname1", "text"),
            ("KUNDENNAME2", "kundenname2", "text"),
            ("AMTLKZ", "amtlkz", "text"),
            ("MODELLBEZEICHNUNG", "modellbezeichnung", "text"),
            ("TELEFONNR1", "telefonnr1", "text"),
            ("TELEFONNR2", "telefonnr2", "text"),
            ("EINLAGERUNGSTYP", "einlagerungstyp", "text"),
            ("REIFEN_VL", "reifen_vl", "text"),
            ("REIFEN_VR", "reifen_vr", "text"),
            ("REIFEN_HL", "reifen_hl", "text"),
            ("REIFEN_HR", "reifen_hr", "text"),
            ("REIFEN_RR", "reifen_rr", "text"),
            ("FELGE_VL", "felge_vl", "text"),
            ("FELGE_VR", "felge_vr", "text"),
            ("FELGE_HL", "felge_hl", "text"),
            ("FELGE_HR", "felge_hr", "text"),
            ("KAPPE_VL", "kappe_vl", "text"),
            ("KAPPE_VR", "kappe_vr", "text"),
            ("KAPPE_HL", "kappe_hl", "text"),
            ("KAPPE_HR", "kappe_hr", "text"),
            ("RADSCHRAUBENVORHANDEN", "radschraubenvorhanden", "text"),
            ("RADSCHRAUBENANZAHL", "radschraubenanzahl", "text"),
        ],
    },
    "ersatzfzgbelegung": {
        "file_suffix": "ersatzfzgbelegung",
        "columns": [
            ("MOBILITAETBEZ", "mobilitaetbez", "text"),
            ("ERSATZFZGKATEGORIE", "ersatzfzgkategorie", "text"),
            ("FZGKENNUNG", "fzgkennung", "text"),
            ("AMTLKZ", "amtlkz", "text"),
            ("GUELTIGAB", "gueltigab", "datetime"),
            ("GUELTIGBIS", "gueltigbis", "datetime"),
            ("VONZEITPUNKT", "vonzeitpunkt", "datetime"),
            ("BISZEITPUNKT", "biszeitpunkt", "datetime"),
            ("AUFTRAGSNR", "auftragsnr", "auftragsnr"),
            ("NICHTVERFUEGBARKEIT", "nichtverfuegbarkeit", "text"),
            ("FIXIERUNG", "fixierung", "text"),
        ],
    },
    "teilebestand": {
        "file_suffix": "teilebestand",
        "columns": [
            ("FABRIKATGRUPPE", "fabrikatgruppe", "text"),
            ("TEILENUMMER", "teilenummer", "text"),
            ("TEILEBEZEICHNUNG", "teilebezeichnung", "text"),
            ("GESAMTBESTANDSMENGE", "gesamtbestandsmenge", "decimal3"),
            ("SUBLAGERNR", "sublagernr", "text"),
            ("LAGERORTNEU", "lagerortneu", "text"),
            ("BESTANDNEU", "bestandneu", "decimal3"),
            ("VERKAUFSPREIS", "verkaufspreis", "decimal2"),
            ("WARENART", "warenart", "text"),
            ("RABATTGRUPPE", "rabattgruppe", "text"),
        ],
    },
}


def _finalize(kind, raw_value):
    if kind == "text":
        return convert.clean_text(raw_value)
    if kind == "date":
        return convert.to_date(raw_value)
    if kind == "datetime":
        return convert.to_datetime(raw_value)
    if kind in ("decimal2", "decimal3"):
        return convert.parse_decimal(raw_value)
    if kind == "auftragsnr":
        return convert.coerce_auftragsnr(raw_value)
    return raw_value


def _stringify_raw(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    return str(value)


def build_rows(table_key, headers, data_rows):
    """Wandelt die rohen Zeilen einer .xls-Datei in fertige DB-Zeilen um.

    Spalten werden ueber den normalisierten Header gesucht, nicht ueber ihre
    Position -- die Reihenfolge der Spalten im DMS-Export ist damit egal.
    Fehlt eine erwartete Spalte komplett, wird das als harter Fehler
    behandelt (bricht den Import fuer diesen Betrieb ab, siehe run_import),
    weil das auf eine strukturelle Aenderung des Exportformats hindeutet.
    """
    spec = TABLES[table_key]

    normalized_lookup = {}
    for idx, header in enumerate(headers):
        for variant in convert.normalize_header_variants(header):
            normalized_lookup.setdefault(variant, idx)

    col_index = {}
    missing = []
    for source_header, db_col, kind in spec["columns"]:
        idx = normalized_lookup.get(convert.normalize_header(source_header))
        if idx is None:
            missing.append(source_header)
        col_index[db_col] = idx

    if missing:
        raise ValueError(
            f"Tabelle '{table_key}': erwartete Spalte(n) nicht gefunden: {', '.join(missing)}"
        )

    results = []
    for row in data_rows:
        typed = {}
        raw = {}
        for source_header, db_col, kind in spec["columns"]:
            idx = col_index[db_col]
            raw_value = row[idx] if idx < len(row) else None
            typed[db_col] = _finalize(kind, raw_value)
            raw[source_header] = _stringify_raw(raw_value)
        typed["raw_row"] = raw
        results.append(typed)
    return results
