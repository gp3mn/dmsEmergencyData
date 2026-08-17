# Umsetzungsbeschreibung: Notfall-Datenportal für DMS-Exportdaten

## Kontext

Das DMS liefert täglich **je Betrieb eine eigene ZIP-Datei** mit Notfalldaten (Aufträge, Positionen, Reifeneinlagerung, Ersatzfahrzeugbelegung, Teilebestand) als klassische Excel-`.xls`-Dateien (altes BIFF/OLE2-Format, bestätigt per `file` als "CDFV2 Microsoft Excel"). Fällt das eigentliche DMS aus, sollen Mitarbeitende trotzdem Aufträge recherchieren, Details einsehen und ausdrucken können. Aktuell existiert im Projektverzeichnis nur `anforderung.md` und eine Beispiel-ZIP unter `import/20260817000745_notfall.48755.zip` — es wird komplett neuer Code erstellt.

Der Dateiname ist logisch aufgebaut: `20260817000745_notfall.48755.zip` → `20260817` = Datenstand (Datum, zu dem die Daten exportiert wurden), `000745` = Uhrzeit, `48755` = Betriebsnummer. Da mehrere Betriebe jeweils eine eigene ZIP liefern, muss das System **mehrere Betriebe getrennt verwalten**: Import, Datenhaltung und Recherche laufen pro Betrieb isoliert, und der Anwender wählt in der Oberfläche aus, für welchen Betrieb er Daten sehen möchte.

Die Beispiel-ZIP wurde inspiziert (Python `zipfile` + `strings`, kein Code geschrieben) und enthält fünf Tabellen mit folgenden Spalten:

- **auftragskopf** (Auftragsköpfe, Schlüssel `AUFTRAGSNR`): Annahme-/Abhol-/Fertigstellungs-/Rückgabe-/Zustelldaten, Kunde, Fahrzeug (FGSTNR, AMTLKZ, Modell), Ersatzfahrzeug, Rechnungsstatus, Stempelungen/Arbeitszeiten (~49 Spalten)
- **auftragspositionen** (größte Datei, ~2,4 MB): Arbeiten & Teile je Auftrag, referenziert über AUFTRAGSNR/SUBAUFTRAGSNR/POSITIONSKZ
- **einlagerungen**: Reifen-/Radeinlagerung je Auftrag (aktuell fast leer, ~6 KB)
- **ersatzfzgbelegung**: Ersatzfahrzeug-Belegungszeiträume, Datum/Zeit als Text `DD-MM-YYYY HH:MM`
- **teilebestand**: Teilebestand/Lager, unabhängig vom Auftrag, Beträge als deutsche Komma-Dezimalzahlen im Text (z.B. `"248,6"`)

Getroffene Entscheidungen (mit dem Auftraggeber abgestimmt):

- **Stack**: Python (Flask, serverseitig gerendert mit Jinja2) + PostgreSQL, genau 2 Docker-Services (web + db)
- **Minimal-Library-Vorgabe gilt fürs Frontend**: kein React/Vue/Bootstrap/jQuery — nur handgeschriebenes HTML/CSS/JS. Backend-Abhängigkeiten sind vertretbar, wenn nötig: `xlrd` ist die einzige praktikable Bibliothek für altes BIFF-`.xls` (pandas/openpyxl unterstützen es nicht), `psycopg2-binary` als DB-Treiber, `gunicorn` zum Ausliefern. Kein APScheduler — periodischer Scan läuft als simpler Background-Thread.
- **Import-Trigger**: automatisch über gemounteten `import/`-Ordner + periodischer Scan-Thread im Web-Container, zusätzlich Button „Jetzt importieren“ als manueller Fallback. Ein Scan-Durchlauf verarbeitet **alle** ausstehenden ZIPs (mehrere Betriebe) in einem Durchgang.
- **Datenhaltung**: kein zeitlicher Verlauf — jeder Import ersetzt den vorherigen Datenstand, aber **nur für den betroffenen Betrieb** (die Daten anderer Betriebe bleiben unangetastet).
- **Mandantenfähigkeit**: jede Tabelle trägt eine `betrieb`-Spalte (Betriebsnummer aus dem Dateinamen); alle Abfragen sind auf den in der Oberfläche gewählten Betrieb beschränkt.
- **Zugriffsschutz**: ein gemeinsamer Login (Username/Passwort), Session-Cookie-basiert; nach dem Login wählt der Anwender den Betrieb, danach ist die Auswahl in der Session gespeichert und über die Navigation wechselbar.
- **Kernflows**: Betriebsauswahl (Startseite), Auftragssuche (Auftragsnr, Kundenname, Kennzeichen, Fahrgestellnr, Datumsbereich) innerhalb des gewählten Betriebs, Auftragsdetail (Kopf + Positionen + ggf. Einlagerung/Ersatzfahrzeug), Druckansicht (Browser-`window.print()` + `@media print`, keine PDF-Lib). Zusätzlich einfache Teilebestand-Suche je Betrieb.

## Wichtige technische Fallstricke (vor Implementierung beachten)

- `xlrd` ist lokal noch nicht installierbar getestet worden (Sandbox ohne Paketzugriff) — die genaue Zelltyp-Erkennung muss defensiv implementiert werden, nicht angenommen.
- Datumsfelder sind vermutlich **inkonsistent typisiert**: in `ersatzfzgbelegung` als Text (`DD-MM-YYYY HH:MM`, per `strings` bestätigt), in `auftragskopf` vermutlich als echte Excel-Datums-Zellen (kein Datumstext im String-Table gefunden). Der Importer braucht zwei Dekodierpfade (numerische Zelle via `xlrd.xldate_as_datetime` **und** Text-Pattern-Matching als Fallback) statt sich auf `cell.ctype` allein zu verlassen.
- `AUFTRAGSNR` kommt vermutlich als `float` aus xlrd (z.B. `48755.0`) — muss konsistent zu `text`/`int` normalisiert werden, sonst brechen Joins zwischen den 5 Tabellen. `AUFTRAGSNR` ist nur **innerhalb eines Betriebs** eindeutig, nicht betriebsübergreifend — der Primärschlüssel muss daher immer `(betrieb, auftragsnr)` sein, nie `auftragsnr` allein.
- Beträge sind deutsche Komma-Dezimalzahlen als Text (`"248,6"`, ggf. `"1.234,56"` mit Tausenderpunkt) — eigener Parser nötig.
- `einlagerungen.xls` ist fast leer — Importer muss leere/kopfzeilennur Sheets tolerieren.

## Mandantenfähigkeit (mehrere Betriebe)

**Dateiname-Parsing** (`app/importer/filename.py` oder Teil von `scanner.py`): Regex `^(\d{8})(\d{6})_notfall\.(\d+)\.zip$` extrahiert Datenstand-Datum (`YYYYMMDD`), Uhrzeit (`HHMMSS`) und Betriebsnummer. Dateien, die nicht auf dieses Muster passen, werden ignoriert und geloggt (kein Absturz bei unerwarteten Dateien im Ordner).

**Scan-Ablauf pro Tick** (`scanner.scan_once()`):
1. Alle `import/*.zip` auflisten, per Regex in `(datenstand, betrieb, zip_path)` zerlegen.
2. Nach `betrieb` gruppieren; pro Betrieb nur die **neueste** noch nicht importierte Datei verwenden (ältere ausstehende Dateien desselben Betriebs werden als `skipped_superseded` markiert, da jeder Import ohnehin ein Vollersatz für diesen Betrieb ist).
3. Für jeden Betrieb mit einer neuen Datei: Import unabhängig von den anderen Betrieben durchführen (ein Fehler bei Betrieb A darf Betrieb B nicht blockieren) — je Betrieb eigener Try/Except-Block und eigener `import_log`-Eintrag.

**Import je Betrieb** (statt globalem `TRUNCATE`): innerhalb einer Transaktion `DELETE FROM <tabelle> WHERE betrieb = :betrieb` gefolgt vom Bulk-Insert der neuen Zeilen (alle mit `betrieb = :betrieb` getaggt), für alle 5 Tabellen. Commit erst wenn alle 5 Tabellen für diesen Betrieb fehlerfrei ersetzt wurden; bei Fehler Rollback, Daten des Betriebs bleiben auf dem alten Stand.

**`betriebe`-Tabelle** wird bei jedem erfolgreichen Import upsertet (Betriebsnummer, Datenstand-Datum, letzter Import-Zeitpunkt, letzter Status) und ist die Grundlage für die Betriebsauswahl auf der Startseite. Firmenname, Standortbezeichnung, Adresse und Telefon liefert der Notfall-Export nicht — diese Felder sind daher manuell über `/betrieb/<nr>/bearbeiten` zu pflegen (siehe unten) und bleiben bis dahin leer, ohne dass das sonst funktionierende System davon beeinträchtigt wird.

**UI-Ablauf**: Nach dem Login landet der Anwender auf `/betriebe` (Startseite/Betriebsauswahl) — einer Tabelle aller bekannten Betriebe mit Betriebsnummer, Datenstand, letztem Import-Zeitpunkt/-Status. Klick auf einen Betrieb setzt `session['betrieb']` und leitet zu `/suche` weiter. Die Navigation zeigt danach immer den aktuell gewählten Betrieb + Datenstand sowie einen Link „Betrieb wechseln“ zurück zu `/betriebe`. Alle Routen (`/suche`, `/auftrag/<nr>`, `/teilebestand`) prüfen, dass ein Betrieb in der Session gewählt ist, und filtern sämtliche Datenbankabfragen zusätzlich mit `WHERE betrieb = :betrieb` — sonst Redirect zu `/betriebe`.

## Datenbankschema (PostgreSQL)

Prinzip: **weiche Referenzen statt Fremdschlüssel** zwischen den Datentabellen (AUFTRAGSNR als indexierte `text`-Spalte, keine `REFERENCES`-Constraints), da `einlagerungen`/`ersatzfzgbelegung` auf Aufträge verweisen können, die im aktuellen Snapshot ggf. nicht (mehr) existieren. Jede Datentabelle bekommt zusätzlich eine `raw_row jsonb`-Spalte als Sicherheitsnetz (falls die typisierte Spalten-Konvertierung bei einzelnen Zeilen scheitert, bleibt die Rohzeile erhalten statt Datenverlust) sowie eine **`betrieb text NOT NULL`-Spalte** zur Mandantentrennung.

Tabellen (DDL in `db/init.sql`, wird beim ersten Start via Postgres-`docker-entrypoint-initdb.d` angelegt):

- `betriebe` — PK `betriebsnummer text`, `firmenname text NULL` (rechtliche Unternehmensbezeichnung, z.B. Konzern-/Mandantenname — erscheint als Dokumentkopf im Ausdruck), `name text NULL` (Standortbezeichnung, z.B. Filiale/Marke), `strasse text NULL`, `plz_ort text NULL`, `telefon text NULL`, `letzter_datenstand date`, `letzter_import_at timestamptz`, `letzter_status text`
- `auftraege` — **Composite-PK `(betrieb, auftragsnr)`**, alle ~48 Felder aus auftragskopf (Datumsfelder als `date`, Uhrzeiten als `text`, Beträge als `numeric`), Indizes auf `(betrieb, lower(kundenname))`, `(betrieb, lower(amtlkz))`, `(betrieb, lower(fgstnr))`, `(betrieb, annahmedatum)`. Die Spalten `MOBILIT...` und `TSART` aus der ursprünglichen Spaltenliste stellten sich als **eine** Spalte `MOBILITAETSART` heraus (siehe „Implementierungs-Erkenntnisse“) und wurden entsprechend als `mobilitaetsart` zusammengeführt.
- `auftragspositionen` — Surrogat-PK `bigserial` (SUBAUFTRAGSNR+POSITIONSKZ ist nicht sicher eindeutig), Spalte `betrieb`, Index auf `(betrieb, auftragsnr)`
- `einlagerungen` — Surrogat-PK, Spalte `betrieb`, Index auf `(betrieb, auftragsnr)`
- `ersatzfzgbelegung` — Surrogat-PK, Spalte `betrieb`, Zeiträume als `timestamp` (naiv, ohne Zeitzone — Quelle liefert implizit Europe/Berlin ohne Zeitzonenangabe), Index auf `(betrieb, auftragsnr)`
- `teilebestand` — Surrogat-PK, Spalte `betrieb`, Index auf `(betrieb, teilenummer)` und `(betrieb, lower(teilebezeichnung))`
- `import_log` — `betrieb`, `zip_filename`, `datenstand date` (aus Dateiname geparst), `started_at`/`finished_at`, `status` (running/success/failed/skipped_superseded), `error_message`, Zeilenzahlen pro Tabelle, `triggered_by` (scanner/manual:\<user\>)

## Projektstruktur & Flask-App

```
crossNotfall/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt        # flask, psycopg2-binary, xlrd, gunicorn
├── .env.example
├── db/init.sql
├── import/                 # bind mount, DMS legt hier ZIPs ab (mehrere Betriebe)
│   └── processed/          # archivierte, erfolgreich importierte ZIPs
└── app/
    ├── __init__.py         # create_app(), startet Scanner-Thread einmalig
    ├── config.py
    ├── db.py                # psycopg2-Connection-Helper
    ├── auth.py              # /login (ENV-Fallback + benutzer-Tabelle), /logout
    ├── auth_context.py      # require_erweitert-Decorator (blockt Rolle 'standard')
    ├── betrieb_context.py   # require_betrieb-Decorator, liest/schreibt session['betrieb']
    ├── scanner.py           # Background-Thread, scan-Intervall aus ENV, Dateiname-Parsing
    ├── importer/
    │   ├── xls_reader.py    # xlrd-Wrapper, Header-Lookup statt Positionsannahme
    │   ├── convert.py       # Datum/Zeit dual-path, Komma-Dezimal-Parser, AUFTRAGSNR-Coercion
    │   ├── schema.py        # Spalten-Mapping + Insert-SQL je Tabelle
    │   └── run_import.py    # Orchestrierung je Betrieb: unzip -> parsen -> 1 Transaktion -> archivieren
    ├── routes/
    │   ├── betrieb.py         # GET /betriebe, POST /betrieb/<nr>/waehlen, GET/POST /betrieb/<nr>/bearbeiten
    │   ├── search.py          # GET /suche
    │   ├── auftrag.py         # GET /auftrag/<nr>, GET /auftrag/<nr>/druck
    │   ├── teilebestand.py    # GET /teilebestand (+ Checkbox alle Niederlassungen)
    │   ├── einlagerungen.py   # GET /einlagerungen
    │   ├── ersatzfahrzeuge.py # GET /ersatzfahrzeuge
    │   ├── benutzer.py        # GET /admin/benutzer, .../neu, .../<id>/loeschen, .../<id>/passwort (nur Rolle admin)
    │   └── admin.py           # POST /import/jetzt, GET /import/status
    ├── templates/
    │   ├── base.html, login.html
    │   ├── betrieb_auswahl.html, betrieb_bearbeiten.html
    │   ├── benutzer_liste.html, benutzer_neu.html, benutzer_passwort.html
    │   ├── search.html, teilebestand.html, einlagerungen.html, ersatzfahrzeuge.html
    │   ├── auftrag_detail.html, auftrag_print.html
    │   └── _auftrag_dokument.html   # gemeinsamer Dokument-Block (siehe unten)
    └── static/
        ├── style.css (inkl. @media print), print_auftrag.css, app.js
```

**Routen:** `/login`, `/logout`, `/betriebe` (Startseite nach Login: Betriebsauswahl mit Datenstand/Status), `/betrieb/<nr>/waehlen` (POST, setzt Session, redirect zu `/suche`), `/betrieb/<nr>/bearbeiten` (GET/POST, pflegt Firmenname, Standortbezeichnung, Adresse und Telefon, da der Notfall-Export das nicht liefert), `/suche` (Suchformular + Ergebnistabelle, betriebsgebunden), `/auftrag/<auftragsnr>` (Detail), `/auftrag/<auftragsnr>/druck` (Druckansicht ohne Navigation, `window.print()` beim Laden), `/teilebestand` (Teilesuche, standardmäßig betriebsgebunden — Checkbox „Alle Niederlassungen durchsuchen“ hebt den Betriebsfilter für diese eine Suche auf und zeigt zusätzlich eine Niederlassungs-Spalte, damit Teile an anderen Standorten gefunden werden können), `/einlagerungen` (eigene Such-/Listenseite für Reifen-/Radeinlagerungen, betriebsgebunden, zeigt standardmäßig alle Einträge — nötig, da diese sonst nur über einen noch existierenden Auftrag auffindbar wären, siehe Fußnote unten), `/ersatzfahrzeuge` (analoge Such-/Listenseite für Ersatzfahrzeug-Belegungen), `/admin/benutzer` (Benutzerverwaltung: Liste, `.../neu`, `.../<id>/loeschen`, `.../<id>/passwort` — nur Rolle `admin`), `/import/jetzt` (manueller Trigger für alle Betriebe, POST), `/import/status` (letzte Importe, alle Betriebe).

**Einlagerungen/Ersatzfahrzeuge unabhängig vom Auftrag auffindbar:** Da `einlagerungen` und `ersatzfzgbelegung` nur weich auf `auftraege` referenzieren (kein Hard-FK, siehe Datenbankschema), war ein Datensatz bislang nur erreichbar, wenn der zugehörige Auftrag noch im aktuellen Tages-Snapshot enthalten war — ältere/geschlossene Aufträge, die nicht mehr exportiert werden, machten die zugehörige Einlagerung/Belegung faktisch unauffindbar. `/einlagerungen` und `/ersatzfahrzeuge` listen daher unabhängig vom Auftragsstatus alle Einträge des gewählten Betriebs (mit Suchfeld zum Filtern) und verlinken die Auftragsnummer nur dann anklickbar, wenn der Auftrag aktuell noch existiert (per `LEFT JOIN` gegen `auftraege` geprüft).

**Auftragsansicht = Ausdruck-Layout:** Detailseite und Druckansicht rendern denselben Inhalt über das gemeinsame Partial `_auftrag_dokument.html` (Kopfraster, Positionstabelle, rechtlicher Fußtext — nachgebildet nach dem Original-Auftragsdokument aus `vorlagen/`). `auftrag_detail.html` bindet es innerhalb von `base.html` ein (mit Navigation + „Drucken“-Button, zusätzlich `print_auftrag.css` über den `extra_head`-Block), `auftrag_print.html` bindet es standalone ein (kein Nav, `window.print()` beim Laden). Ein Auftrag sieht damit auf dem Bildschirm identisch aus wie im Ausdruck.

**Login & Rollen:** `werkzeug.security.generate_password_hash`/`check_password_hash` (kommt mit Flask, keine Zusatzabhängigkeit). Zwei Wege ins System:
- **ENV-Fallback**: `APP_USERNAME`/`APP_PASSWORD_HASH` aus der Umgebung, wirkt immer als Rolle `admin` ohne Betriebsbindung. Bleibt dauerhaft bestehen, garantiert einen Zugang, falls die Benutzerverwaltung leer ist oder alle DB-Admin-Konten gelöscht wurden.
- **`benutzer`-Tabelle** (`id`, `benutzername` UNIQUE, `passwort_hash`, `rolle` als reiner `text` — `standard`/`erweitert`/`admin`, per Python-Allowlist geprüft, keine DB-Enum/CHECK, konsistent zum Rest des Schemas —, `betrieb` als weiche `text`-Referenz nur bei `rolle=standard`, `erstellt_am`).

Drei Rollen: **Standard** ist fest an genau einen Betrieb gebunden (`session["betrieb"]` wird beim Login aus dem Benutzer-Datensatz gesetzt, Login führt direkt zu `/suche`, kein Zugriff auf Betriebsauswahl/-wechsel möglich), **Erweitert** kann wie bisher über `/betriebe` zwischen allen Betrieben wechseln, **Admin** zusätzlich Zugriff auf die Benutzerverwaltung unter `/admin/benutzer` (anlegen, Passwort zurücksetzen, löschen — bewusst kein nachträgliches Ändern von Rolle/Betrieb, dafür löschen+neu anlegen). Durchgesetzt über `app/auth_context.py`s `require_erweitert`-Decorator (blockt `betrieb.auswahl`/`waehlen`/`bearbeiten` für Standard-Sessions mit `abort(403)`) und einen blueprint-weiten `before_request`-Gate in `routes/benutzer.py` (nur `rolle=="admin"`). Session speichert zusätzlich `rolle` und `benutzer_id`.

**Wichtig für den Betrieb:** Da der Notfall-Export selbst keine Benutzerkonten liefert, muss nach jedem frischen Deployment einmalig über den ENV-Fallback eingeloggt und für jede vorhandene Betriebsnummer ein Standard-Benutzer angelegt werden (`/admin/benutzer/neu`) — das ist ein manueller Datenpflege-Schritt, kein Seed-Skript.

**Background-Scanner unter Gunicorn:** `gunicorn --workers 1 --threads 8` — ein einzelner Worker-Prozess verhindert doppelte Scanner-Threads ohne zusätzliche Locking-Infrastruktur. Der Scanner-Thread startet einmalig beim App-Factory-Aufruf (Guard per `threading.Lock`), läuft als Daemon-Thread mit `while True: scan_once(); sleep(INTERVAL)` und verarbeitet dabei alle Betriebe nacheinander. Zusätzlich als günstige Absicherung ein Postgres-`pg_try_advisory_lock` **je Betrieb** um die eigentliche Import-Transaktion, damit der manuelle „Jetzt importieren“-Button nie mit dem periodischen Thread kollidiert (und Betriebe parallel/unabhängig gesperrt werden können, falls später doch mehrere Worker nötig werden).

## Importer-Logik

1. **Dateiname-Parsing**: Datenstand-Datum + Betriebsnummer aus jedem ZIP-Dateinamen extrahieren (siehe „Mandantenfähigkeit“ oben); Dateien mit unerwartetem Namensmuster werden übersprungen und geloggt.
2. **Header-basiertes Mapping**: Spaltennamen aus Zeile 0 lesen, nicht auf feste Spaltenposition verlassen.
3. **Robuste Zellkonvertierung**: numerische Zelle → Zahlenformat der Zelle prüfen (Datumsmuster?) → `xldate_as_datetime` versuchen; Textzelle → Datums-Pattern (`DD-MM-YYYY[ HH:MM]`) versuchen; scheitert beides, Rohwert in `raw_row` behalten, typisierte Spalte `NULL`, Warnung loggen (kein Hard-Fail für einzelne Zellen).
4. **Gruppierung nach Betrieb**: pro Scan-Tick alle ausstehenden ZIPs nach Betriebsnummer gruppieren, je Betrieb nur die neueste unverarbeitete Datei importieren (ältere → `skipped_superseded`), unabhängige Fehlerbehandlung je Betrieb.
5. **Alles-oder-nichts-Import je Betrieb**: erst alle 5 Dateien einer ZIP vollständig in Python-Strukturen parsen; erst wenn alle 5 fehlerfrei geparst sind, eine einzige DB-Transaktion öffnen (`DELETE ... WHERE betrieb = :betrieb` + Bulk-Insert via `execute_values` je Tabelle), commit. Jeder Fehler vorher oder währenddessen → Rollback, alte Daten dieses Betriebs bleiben unangetastet, andere Betriebe sind ohnehin nicht betroffen, `import_log.status='failed'`.
6. Erfolgreiche ZIP nach `import/processed/` verschieben, `betriebe`-Tabelle upserten; nach 3 aufeinanderfolgenden Fehlversuchen derselben Datei automatisch als `<name>.failed` verschieben, um endloses Retry-Loggen zu vermeiden.

## Docker Compose

- `db`: `postgres:16-alpine`, Volume `db_data`, mountet `db/init.sql` für initiales Schema, Healthcheck `pg_isready`
- `web`: eigenes Dockerfile (python:3.12-slim, installiert requirements.txt), mountet `./import`, ENV für DB-Verbindung/Login/Scan-Intervall, Healthcheck gegen `/login`, `depends_on: db (service_healthy)`

## Frontend (nur Vanilla HTML/CSS/JS)

- **Betriebsauswahl** (`/betriebe`): einfache HTML-Tabelle, ein Link/Button je Zeile (`<form method="post" action="/betrieb/<nr>/waehlen">`), kein JS nötig.
- Sucheformular als normales `<form method="get">` mit vollständigem Seiten-Reload — bewusst **kein** Live-Suchen/Debounce, da Datenmenge klein ist und das der einfachste Weg ist, der die Minimal-JS-Vorgabe erfüllt.
- Einziger sinnvoller JS-Einsatz: „Jetzt importieren“-Button per `fetch()` (kein Reload nötig) und `window.print()`-Aufruf auf der Druckseite.
- Druckansicht: eigenes schlankes Template ohne Navigation, `@media print { .no-print { display:none } }` in `style.css`.
- Bedingte Anzeige von Einlagerung/Ersatzfahrzeug-Blöcken auf der Detailseite nur wenn Daten vorhanden sind (weiche Referenz, nicht garantiert vorhanden).
- Navigation zeigt in jeder betriebsgebundenen Seite den aktuell gewählten Betrieb (Nummer + Datenstand) und einen Link „Betrieb wechseln“.

## Implementierungs-Erkenntnisse (beim Testen mit echten Daten gefunden)

Beim End-to-End-Test mit der Beispiel-ZIP sowie zwei weiteren echten Betriebs-Lieferungen (Betrieb 20570 kam waehrend der Umsetzung als reale zweite Tageslieferung hinzu) zeigten sich vier reale Probleme, die beim reinen Betrachten der Rohdaten (ohne installiertes `xlrd`) nicht erkennbar waren:

1. **`xlrd.open_workbook()` braucht `formatting_info=True`**, sonst liefert xlrd kein Zellformat und Datumszellen lassen sich nicht von Zahlen unterscheiden (`cell.xf_index` bleibt `None`). Behoben in `xls_reader.py`.
2. **`MOBILIT...` und `TSART` waren keine zwei Spalten, sondern eine:** `MOBILITÄTSART`. Der ursprüngliche Verdacht (Umlaut-bedingter Strings-Abbruch) war richtig, nur die Trennung in zwei Felder war falsch. Das DMS dekodiert diesen und einige `RÜCKGABE*`-Spaltennamen mit einem kaputten Umlaut (Unicode-Replacement-Character `�` statt Ä/Ü) — vermutlich ein Codepage-Problem in der Quelldatei. Behoben durch `convert.normalize_header_variants()`, die bei einem Replacement-Character alle plausiblen Umlaut-Varianten (AE/OE/UE/SS) als Kandidaten prueft, statt eine einzige Normalform zu erzwingen. Die Spalte heisst in der DB jetzt `mobilitaetsart`.
3. **Reine Uhrzeit-Zellen (z.B. `ANNAHMEUHRZEIT`) sind ebenfalls `XL_CELL_DATE`**, ihr Zahlenwert ist aber nur ein Tagesbruchteil < 1 ohne sinnvollen Datumsanteil (xlrd würde das auf das Excel-Epoch-Datum ~1899 abbilden, was der Plausibilitäts-Jahresfilter verworfen hätte). Behoben in `xls_reader._safe_xldate()`: Werte < 1 werden als `datetime.time` interpretiert und in `convert.clean_text()` als `HH:MM`-Text ausgegeben statt verworfen.
4. **`AUFTRAGSNR` ist in `auftragskopf` nicht immer eindeutig:** Das Quellsystem liefert je Auftrag mehrere fast identische Kopfzeilen (offenbar eine Zeile je Kombination aus Abhol-/Zustelltermin). Das bestätigt das ursprünglich vermutete Risiko — als pragmatische Lösung dedupliziert der Importer jetzt beim Einlesen von `auftraege` auf die jeweils letzte Zeile je `(betrieb, auftragsnr)` und loggt die Anzahl zusammengeführter Zeilen als Warnung (`run_import._dedupe_auftraege`). Für eine reine Rechercheoberfläche im Notfall ist der Verlust der genauen Logistik-Kombination vertretbar.

Nach diesen vier Korrekturen liefen alle drei getesteten Betriebe (48755, 99999 als künstliche Kopie, 20570 als echte zweite Lieferung) erfolgreich durch, mit korrekter Datentrennung zwischen den Betrieben (siehe Verifikation unten).

## Offene Risiken (bewusst nicht versteckt)

- Die Deduplizierung von `auftraege` (siehe Punkt 4 oben) behält die zeitlich letzte Zeile je Auftrag; welche der Abhol-/Zustellkombinationen das im Detail ist, ist für die Recherche nicht relevant, geht aber nicht mehr aus der DB hervor. `raw_row` enthält nur die zuletzt gewählte Zeile, nicht alle Varianten.
- Keine Zeitzone in den Zeitstempeln (Quelle liefert implizit Europe/Berlin ohne Kennzeichnung).
- Betriebe, die noch nie erfolgreich importiert wurden, tauchen nicht in der Betriebsauswahl auf (die Liste basiert auf der `betriebe`-Tabelle, die nur bei erfolgreichem Import gepflegt wird) — bei einem dauerhaft fehlschlagenden Import für einen neuen Betrieb bleibt dieser für den Anwender unsichtbar, nur über `import_log`/Logs erkennbar. Akzeptiert, da ein Betrieb ohne je erfolgreich importierte Daten ohnehin keine recherchierbaren Inhalte hätte.
- `docker-compose.yml`: `APP_PASSWORD_HASH`/`APP_USERNAME`/`SECRET_KEY` werden bewusst über `env_file: .env` statt über `${VAR}`-Interpolation im `environment`-Block geladen, weil Compose einzelne `$`-Zeichen sonst als (unbekannte) Variablenreferenz interpretiert und den werkzeug-Passwort-Hash (der `$` als Trennzeichen nutzt) an dieser Stelle abschneidet. Wird der Hash dennoch direkt in eine `${...}`-Interpolation eingesetzt, müssen alle `$` darin als `$$` escaped werden (siehe Kommentar in `.env.example`).

## Verifikation

1. Nach Implementierung: `docker compose up --build`, prüfen dass `db` healthy wird, dann `web` startet.
2. Kleines Standalone-Skript zuerst gegen die 5 extrahierten `.xls`-Dateien laufen lassen (`xlrd.open_workbook`, Header + erste Zeilen + `ctype` der Datumsfelder ausgeben), um die Annahmen zu §„Fallstricke“ vor der vollen Importer-Implementierung zu bestätigen.
3. Import der Beispiel-ZIP `import/20260817000745_notfall.48755.zip` auslösen (Scanner-Tick abwarten oder „Jetzt importieren“ klicken), per `docker compose exec db psql` prüfen: `import_log` zeigt `success` für Betrieb `48755`, `betriebe`-Tabelle hat einen Eintrag mit korrektem Datenstand (17.08.2026), Zeilenzahlen in allen 5 Tabellen plausibel.
4. **Mandantentest**: eine Kopie der Beispiel-ZIP unter einem anderen Dateinamen ablegen, z.B. `20260817000900_notfall.99999.zip` (simulierter zweiter Betrieb), Scan erneut auslösen; prüfen dass beide Betriebe unabhängig in `betriebe` erscheinen, Datensätze in allen Tabellen korrekt mit `betrieb='48755'` bzw. `betrieb='99999'` getaggt sind, und ein Import für Betrieb 99999 die Daten von Betrieb 48755 nicht verändert.
5. Stichprobe: eine `AUFTRAGSNR` aus `auftraege` (für einen Betrieb) wählen, prüfen dass zugehörige Zeilen in `auftragspositionen` mit demselben (koerzierten) Schlüssel **und demselben Betrieb** existieren.
6. ZIP erneut scannen lassen → darf nicht doppelt importiert werden (Zeilenzahlen unverändert, kein neuer `import_log`-Eintrag außer bei tatsächlich neuer Datei).
7. Absichtlich defekte ZIP-Kopie für einen Betrieb einspielen → Import für diesen Betrieb muss sauber fehlschlagen, Daten dieses **und** aller anderen Betriebe bleiben unverändert.
8. Im Browser: Login-Zwang prüfen (nicht eingeloggt → Redirect), Betriebsauswahl zeigt beide Test-Betriebe mit korrektem Datenstand, Auswahl eines Betriebs führt zu `/suche` und filtert Ergebnisse korrekt (Wechsel zum anderen Betrieb zeigt andere Auftragsnummern), Auftragsdetail öffnen, Druckansicht öffnen (Browser-Druckvorschau prüfen, keine Navigation sichtbar), Teilebestand-Suche mit Komma-Dezimalwerten prüfen, „Jetzt importieren“-Button testen.

## Kritische Dateien

- `app/importer/xls_reader.py`, `app/importer/convert.py`, `app/importer/run_import.py`
- `app/scanner.py`
- `app/betrieb_context.py`, `app/routes/betrieb.py`
- `db/init.sql`
- `docker-compose.yml`, `Dockerfile`
