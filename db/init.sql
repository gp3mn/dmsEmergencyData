-- Schema fuer das Notfall-Datenportal.
-- Wird beim ersten Start des db-Containers automatisch ausgefuehrt
-- (Postgres-Image fuehrt alles unter /docker-entrypoint-initdb.d/ auf einem
-- leeren Datenverzeichnis genau einmal aus).

CREATE TABLE betriebe (
    betriebsnummer      text PRIMARY KEY,
    firmenname          text,
    name                text,
    strasse             text,
    plz_ort             text,
    telefon             text,
    letzter_datenstand  date,
    letzter_import_at   timestamptz,
    letzter_status      text
);

CREATE TABLE auftraege (
    betrieb                   text NOT NULL,
    auftragsnr                text NOT NULL,
    annahmedatum              date,
    annahmeuhrzeit            text,
    annahmeart                text,
    annahmesb                 text,
    auftragstyp               text,
    kundenname                text,
    fahrer                    text,
    amtlkz                    text,
    fahrzeugmodell            text,
    adressekunde              text,
    telefonnr1                text,
    telefonnr2                text,
    marke                     text,
    fgstnr                    text,
    abholdatum                date,
    abholuhrzeit              text,
    abholer                   text,
    abholbemerkung            text,
    annahmebemerkung          text,
    verantwortlsb             text,
    mobilitaetsart            text,
    ersatzfahrzeug            text,
    fertigstellungsdatum      date,
    fertigstellungsuhrzeit    text,
    rueckgabeart              text,
    rueckgabedatum            date,
    rueckgabeuhrzeit          text,
    rueckgabesb               text,
    rueckgabebemerkung        text,
    zustelldatum              date,
    zustelluhrzeit            text,
    zusteller                 text,
    zustellbemerkung          text,
    kundebrutto               numeric(12, 2),
    rechnungsstatus           text,
    kundewartet               text,
    durchfstatus              text,
    wiederholreparatur        text,
    stempelung_datum          date,
    stempelung_startzeit      text,
    stempelung_endzeit        text,
    stempelung_auftragfertig  text,
    stempelung_anmerkung      text,
    stempelung_mechanikernr   text,
    arbeitszeit_gesamt        numeric(10, 2),
    arbeitszeit_gestempelt    numeric(10, 2),
    raw_row                   jsonb,
    imported_at               timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (betrieb, auftragsnr)
);

CREATE INDEX ix_auftraege_kundenname   ON auftraege (betrieb, lower(kundenname));
CREATE INDEX ix_auftraege_amtlkz       ON auftraege (betrieb, lower(amtlkz));
CREATE INDEX ix_auftraege_fgstnr       ON auftraege (betrieb, lower(fgstnr));
CREATE INDEX ix_auftraege_annahmedatum ON auftraege (betrieb, annahmedatum);

CREATE TABLE auftragspositionen (
    id              bigserial PRIMARY KEY,
    betrieb         text NOT NULL,
    reparaturdatum  date,
    annahmesb       text,
    verantwortlsb   text,
    auftragsnr      text,
    subauftragsnr   text,
    auftragstyp     text,
    auftragsart     text,
    positionskz     text,
    identifier      text,
    bezeichnung     text,
    menge           numeric(10, 3),
    zeiteinheiten   numeric(10, 3),
    freiertext      text,
    planungsgrpnr   text,
    planungsgrpbez  text,
    raw_row         jsonb,
    imported_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ix_auftragspositionen_auftragsnr ON auftragspositionen (betrieb, auftragsnr);

CREATE TABLE einlagerungen (
    id                     bigserial PRIMARY KEY,
    betrieb                text NOT NULL,
    lagerort               text,
    depotnr                text,
    status                 text,
    auftragsnr             text,
    kundenname1            text,
    kundenname2            text,
    amtlkz                 text,
    modellbezeichnung      text,
    telefonnr1             text,
    telefonnr2             text,
    einlagerungstyp        text,
    reifen_vl              text,
    reifen_vr              text,
    reifen_hl              text,
    reifen_hr              text,
    reifen_rr              text,
    felge_vl               text,
    felge_vr               text,
    felge_hl               text,
    felge_hr               text,
    kappe_vl               text,
    kappe_vr               text,
    kappe_hl               text,
    kappe_hr               text,
    radschraubenvorhanden  text,
    radschraubenanzahl     text,
    raw_row                jsonb,
    imported_at            timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ix_einlagerungen_auftragsnr ON einlagerungen (betrieb, auftragsnr);

CREATE TABLE ersatzfzgbelegung (
    id                   bigserial PRIMARY KEY,
    betrieb              text NOT NULL,
    mobilitaetbez        text,
    ersatzfzgkategorie   text,
    fzgkennung           text,
    amtlkz               text,
    gueltigab            timestamp,
    gueltigbis           timestamp,
    vonzeitpunkt         timestamp,
    biszeitpunkt         timestamp,
    auftragsnr           text,
    nichtverfuegbarkeit  text,
    fixierung            text,
    raw_row              jsonb,
    imported_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ix_ersatzfzgbelegung_auftragsnr ON ersatzfzgbelegung (betrieb, auftragsnr);

CREATE TABLE teilebestand (
    id                   bigserial PRIMARY KEY,
    betrieb              text NOT NULL,
    fabrikatgruppe       text,
    teilenummer          text,
    teilebezeichnung     text,
    gesamtbestandsmenge  numeric(12, 3),
    sublagernr           text,
    lagerortneu          text,
    bestandneu           numeric(12, 3),
    verkaufspreis        numeric(12, 2),
    warenart             text,
    rabattgruppe         text,
    raw_row              jsonb,
    imported_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ix_teilebestand_teilenummer  ON teilebestand (betrieb, teilenummer);
CREATE INDEX ix_teilebestand_bezeichnung  ON teilebestand (betrieb, lower(teilebezeichnung));

CREATE TABLE import_log (
    id                        bigserial PRIMARY KEY,
    betrieb                   text,
    zip_filename              text NOT NULL,
    datenstand                date,
    started_at                timestamptz NOT NULL DEFAULT now(),
    finished_at               timestamptz,
    status                    text NOT NULL DEFAULT 'running',
    error_message             text,
    rows_auftraege            integer,
    rows_auftragspositionen   integer,
    rows_einlagerungen        integer,
    rows_ersatzfzgbelegung    integer,
    rows_teilebestand         integer,
    triggered_by              text
);

CREATE INDEX ix_import_log_status   ON import_log (status, started_at DESC);
CREATE INDEX ix_import_log_filename ON import_log (zip_filename);

CREATE TABLE benutzer (
    id             bigserial PRIMARY KEY,
    benutzername   text NOT NULL UNIQUE,
    passwort_hash  text NOT NULL,
    rolle          text NOT NULL,        -- 'standard' | 'erweitert' | 'admin', per Python-Allowlist validiert
    betrieb        text,                 -- nur bei rolle='standard' gesetzt; bewusst ohne FK, analog zu den
                                          -- anderen weichen betrieb-Spalten (Benutzer muss fuer eine Betriebs-
                                          -- nummer anlegbar sein, bevor deren erster Import je gelaufen ist)
    erstellt_am    timestamptz NOT NULL DEFAULT now()
);
