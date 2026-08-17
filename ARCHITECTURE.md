# Architektur & Gotchas: Notfall-Datenportal

Technische Hintergrunddokumentation für Entwickler:innen. Für Einrichtung
und Bedienung siehe `README.md`.

## Systemüberblick

- **Stack**: Python (Flask, serverseitig gerendert mit Jinja2) + PostgreSQL, zwei Docker-Services (`web` + `db`).
- **Frontend**: bewusst kein React/Vue/Bootstrap/jQuery — nur handgeschriebenes HTML/CSS/JS. Backend-Abhängigkeiten sind vertretbar, wenn nötig: `xlrd` ist die einzige praktikable Bibliothek für altes BIFF-`.xls` (pandas/openpyxl unterstützen dieses Format nicht), `psycopg2-binary` als DB-Treiber, `gunicorn` zum Ausliefern. Kein APScheduler — der periodische Import-Scan läuft als einfacher Background-Thread.
- **Mandantenfähigkeit**: Das DMS liefert täglich je Betrieb eine eigene ZIP-Datei. Der Dateiname kodiert Datenstand und Betriebsnummer: `JJJJMMTTHHMMSS_notfall.<Betriebsnummer>.zip`. Jede Datentabelle trägt eine `betrieb`-Spalte; alle Abfragen sind auf den in der Session gewählten Betrieb beschränkt.
- **Datenhaltung**: kein zeitlicher Verlauf — jeder Import ersetzt den vorherigen Datenstand, aber nur für den betroffenen Betrieb (andere Betriebe bleiben unangetastet).

## Datenbankschema (PostgreSQL)

Prinzip: **weiche Referenzen statt Fremdschlüssel** zwischen den Datentabellen (`betrieb`/`auftragsnr` als indexierte `text`-Spalten, keine `REFERENCES`-Constraints). Grund: `einlagerungen`/`ersatzfzgbelegung`/`benutzer` können auf einen Betrieb bzw. Auftrag verweisen, der im aktuellen Snapshot (noch) nicht existiert (z.B. ein Standard-Benutzer für eine Betriebsnummer, bevor deren erster Import gelaufen ist). Jede Datentabelle hat zusätzlich eine `raw_row jsonb`-Spalte als Sicherheitsnetz (falls die typisierte Spalten-Konvertierung bei einzelnen Zeilen scheitert, bleibt die Rohzeile erhalten statt Datenverlust).

Tabellen (DDL in `db/init.sql`):

- `betriebe` — PK `betriebsnummer text`, `firmenname`/`name`/`strasse`/`plz_ort`/`telefon` (manuell gepflegt, liefert der Export nicht), `letzter_datenstand`, `letzter_import_at`, `letzter_status`.
- `auftraege` — **Composite-PK `(betrieb, auftragsnr)`** (AUFTRAGSNR ist nur innerhalb eines Betriebs eindeutig, nie betriebsübergreifend als alleiniger Schlüssel verwenden). ~48 Felder aus `auftragskopf`, Datumsfelder als `date`, Uhrzeiten als `text`, Beträge als `numeric`.
- `auftragspositionen` — Surrogat-PK `bigserial` (SUBAUFTRAGSNR+POSITIONSKZ ist nicht sicher eindeutig), Index auf `(betrieb, auftragsnr)`.
- `einlagerungen`, `ersatzfzgbelegung`, `teilebestand` — Surrogat-PK, jeweils indexiert auf `betrieb` + fachlichem Schlüssel.
- `import_log` — Protokoll je Importversuch: `betrieb`, `zip_filename`, `datenstand`, `status` (running/success/failed/skipped_superseded), `error_message`, Zeilenzahlen je Tabelle, `triggered_by`.
- `benutzer` — `id`, `benutzername` UNIQUE, `passwort_hash`, `rolle` (reiner `text`: `standard`/`erweitert`/`admin`, per Python-Allowlist geprüft — bewusst kein DB-Enum/CHECK, konsistent zum Rest des Schemas), `betrieb` (weiche Referenz, nur bei `rolle=standard` gesetzt).

## Import-Pipeline

1. **Dateiname-Parsing**: Regex extrahiert Datenstand-Datum und Betriebsnummer; Dateien mit unerwartetem Namensmuster werden übersprungen und geloggt.
2. **Scan-Ablauf** (`scanner.scan_once()`): alle `import/*.zip` nach Betrieb gruppieren, pro Betrieb nur die neueste unverarbeitete Datei importieren (ältere → `skipped_superseded`, da jeder Import ein Vollersatz ist), unabhängige Fehlerbehandlung je Betrieb (ein Fehler bei Betrieb A blockt Betrieb B nicht).
3. **Header-basiertes Mapping**: Spaltennamen aus Zeile 0 lesen, nie auf feste Spaltenposition verlassen.
4. **Alles-oder-nichts je Betrieb**: erst alle 5 Dateien vollständig parsen; erst wenn das gelingt, eine DB-Transaktion öffnen (`DELETE ... WHERE betrieb = :betrieb` + Bulk-Insert je Tabelle), dann commit. Jeder Fehler davor/dabei → Rollback, alte Daten des Betriebs bleiben unangetastet.
5. Erfolgreiche ZIP nach `import/processed/` verschieben, `betriebe`-Tabelle upserten. Nach 3 aufeinanderfolgenden Fehlversuchen derselben Datei wird sie automatisch als `<name>.zip.failed` markiert (kein endloses Retry-Loggen).
6. **Scanner unter Gunicorn**: `--workers 1 --threads 8` — ein einzelner Worker-Prozess verhindert doppelte Scanner-Threads ohne Locking-Infrastruktur. Zusätzlich ein Postgres-`pg_try_advisory_lock` je Betrieb um die Import-Transaktion, damit der manuelle „Jetzt importieren“-Button nie mit dem periodischen Thread kollidiert.

## Login & Rollen

Zwei Wege ins System:
- **ENV-Fallback** (`APP_USERNAME`/`APP_PASSWORD_HASH`): wirkt immer als Rolle `admin` ohne Betriebsbindung, bleibt dauerhaft bestehen als Notfall-Zugang.
- **`benutzer`-Tabelle**: drei Rollen — **Standard** ist fest an einen Betrieb gebunden (`session["betrieb"]` wird beim Login aus dem Benutzer-Datensatz gesetzt, Login führt direkt zu `/suche`, kein Zugriff auf Betriebsauswahl/-wechsel), **Erweitert** kann über `/betriebe` zwischen allen Betrieben wechseln, **Admin** zusätzlich Zugriff auf die Benutzerverwaltung (`/admin/benutzer`: anlegen, Passwort zurücksetzen, löschen — bewusst kein nachträgliches Ändern von Rolle/Betrieb).

Durchgesetzt über `app/auth_context.py`s `require_erweitert`-Decorator (`abort(403)` für Rolle `standard` auf `betrieb.auswahl`/`waehlen`/`bearbeiten`) und einen blueprint-weiten `before_request`-Gate in `routes/benutzer.py` (nur `rolle=="admin"`). Kein CSRF-Schutz irgendwo in der App (akzeptiertes Risiko für ein internes Tool in einem abgesicherten Netzwerk).

## Auftragsansicht & Ausdruck

Detailseite und Druckansicht rendern denselben Inhalt über das gemeinsame Partial `_auftrag_dokument.html`, damit ein Auftrag auf dem Bildschirm identisch aussieht wie im Ausdruck. `auftrag_detail.html` bindet es innerhalb von `base.html` ein (Navigation + „Drucken“-Button), `auftrag_print.html` standalone (kein Nav, `window.print()` beim Laden). Layout nachgebildet nach einem realen Original-Auftragsdokument des Auftraggebers (nicht Teil dieses Repos).

Eine Fußzeile mit korrekter laufender Seitenzahl je Druckseite wurde geprüft und wieder verworfen: Browser paginieren erst intern im Druck-Renderer und geben das nicht an die Webseite weiter, ein `position:fixed`-Element wiederholt sich beim Drucken **nicht** zuverlässig auf jeder Seite (rendert nur einmal an einer festen Koordinate im Gesamtdokument). Für eine echte Lösung wäre serverseitige PDF-Erzeugung nötig — bewusst nicht umgesetzt, um keine neue Backend-Abhängigkeit einzuführen.

## Einlagerungen/Ersatzfahrzeuge unabhängig vom Auftrag

Da `einlagerungen`/`ersatzfzgbelegung` nur weich auf `auftraege` referenzieren, wäre ein Datensatz sonst nur erreichbar, wenn der zugehörige Auftrag noch im aktuellen Tages-Snapshot enthalten ist — ältere/geschlossene Aufträge machen den Datensatz sonst faktisch unauffindbar. `/einlagerungen` und `/ersatzfahrzeuge` listen daher unabhängig vom Auftragsstatus alle Einträge des gewählten Betriebs; die Auftragsnummer ist nur anklickbar, wenn der Auftrag aktuell noch existiert (per `LEFT JOIN` gegen `auftraege` geprüft).

## Bekannte Gotchas (xlrd & Datenqualität)

Beim Testen mit echten Daten (nicht nur der mitgelieferten Beispiel-ZIP) zeigten sich vier Probleme, die bei reiner Betrachtung der Rohdaten ohne installiertes `xlrd` nicht erkennbar waren:

1. **`xlrd.open_workbook()` braucht `formatting_info=True`**, sonst liefert xlrd kein Zellformat und Datumszellen lassen sich nicht von reinen Zahlen unterscheiden (`cell.xf_index` bleibt sonst `None`). Behoben in `xls_reader.py`.
2. **Manche Spaltennamen enthielten keinen echten Umlaut, sondern einen Unicode-Replacement-Character (`�`)** anstelle von Ä/Ü — vermutlich ein Codepage-Problem in der Quelldatei. Eine vermeintlich zweigeteilte Spalte stellte sich dadurch als eine einzige Spalte heraus (`MOBILITÄTSART`, nicht zwei Felder). Behoben durch `convert.normalize_header_variants()`: bei einem Replacement-Character werden alle plausiblen Umlaut-Varianten (AE/OE/UE/SS) als Kandidaten geprüft, statt eine einzige Normalform zu erzwingen.
3. **Reine Uhrzeit-Zellen sind ebenfalls `XL_CELL_DATE`**, ihr Zahlenwert ist aber nur ein Tagesbruchteil < 1 ohne sinnvollen Datumsanteil (xlrd würde das sonst auf das Excel-Epoch-Datum ~1899 abbilden, was ein Plausibilitäts-Jahresfilter verwerfen würde). Behoben in `xls_reader._safe_xldate()`: Werte < 1 werden als `datetime.time` interpretiert und als `HH:MM`-Text ausgegeben statt verworfen.
4. **`AUFTRAGSNR` ist in den Kopfdaten nicht immer eindeutig:** Das Quellsystem liefert je Auftrag mehrere fast identische Kopfzeilen (offenbar eine Zeile je Kombination aus Abhol-/Zustelltermin). Der Importer dedupliziert daher beim Einlesen von `auftraege` auf die jeweils letzte Zeile je `(betrieb, auftragsnr)` und loggt die Anzahl zusammengeführter Zeilen als Warnung (`run_import._dedupe_auftraege`). Für eine reine Rechercheoberfläche im Notfall ist der Verlust der genauen Logistik-Kombination vertretbar.

## Offene Risiken (bewusst nicht versteckt)

- Die Deduplizierung von `auftraege` (siehe Gotcha 4) behält nur die zeitlich letzte Zeile je Auftrag; `raw_row` enthält ebenfalls nur diese, nicht alle ursprünglichen Varianten.
- Keine Zeitzone in den Zeitstempeln (Quelle liefert implizit Europe/Berlin ohne Kennzeichnung).
- Betriebe ohne je erfolgreich importierte Daten tauchen nicht in der Betriebsauswahl auf (basiert auf der `betriebe`-Tabelle, die nur bei erfolgreichem Import gepflegt wird) — akzeptiert, da ein solcher Betrieb ohnehin nichts Recherchierbares hätte.
- `docker-compose.yml`: `APP_PASSWORD_HASH`/`APP_USERNAME`/`SECRET_KEY` werden über `env_file: .env` geladen, nicht über `${VAR}`-Interpolation im `environment`-Block — Compose interpretiert einzelne `$`-Zeichen sonst als Variablenreferenz und schneidet den werkzeug-Passwort-Hash (der `$` als Trennzeichen nutzt) ab. Wird der Hash dennoch direkt interpoliert, müssen alle `$` als `$$` escaped werden (siehe `.env.example`).
- Kein CSRF-Schutz auf mutierenden POST-Routen — akzeptiertes Risiko für ein internes Tool.
- Session-Cookies sind rein client-seitig signiert, kein serverseitiges Revoke: ein gelöschter Benutzer bleibt bis Logout/Session-Ablauf (`PERMANENT_SESSION_LIFETIME`) eingeloggt.

## Kritische Dateien

- `app/importer/xls_reader.py`, `app/importer/convert.py`, `app/importer/schema.py`, `app/importer/run_import.py`
- `app/scanner.py`
- `app/auth.py`, `app/auth_context.py`, `app/betrieb_context.py`
- `app/routes/betrieb.py`, `app/routes/benutzer.py`, `app/routes/einlagerungen.py`, `app/routes/ersatzfahrzeuge.py`
- `app/templates/_auftrag_dokument.html`
- `db/init.sql`
- `docker-compose.yml`, `Dockerfile`
