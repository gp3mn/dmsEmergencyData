# Notfall-Datenportal

Web-Anwendung zur Recherche in DMS-Notfalldaten, falls das eigentliche
Dealer-Management-System (DMS) ausfällt. Mitarbeitende können Aufträge
suchen, Details einsehen, Aufträge ausdrucken sowie Teilebestand,
Reifen-/Radeinlagerungen und Ersatzfahrzeug-Belegungen durchsuchen.
Mandantenfähig: mehrere Betriebe/Niederlassungen werden getrennt verwaltet.

Technischer Hintergrund und Implementierungsdetails: siehe `UMSETZUNG.md`.

## Voraussetzungen

- Docker und Docker Compose (`docker compose version`)
- Ein Ordner, in den das DMS täglich die Notfall-ZIP-Dateien ablegt (Standard: `./import`)

## Erste Einrichtung

1. `.env`-Datei aus der Vorlage anlegen:

   ```bash
   cp .env.example .env
   ```

2. In `.env` folgende Werte setzen:

   | Variable | Bedeutung |
   |---|---|
   | `POSTGRES_PASSWORD` | Passwort für die PostgreSQL-Datenbank (frei wählbar) |
   | `APP_USERNAME` | Benutzername des dauerhaften Notfall-Admin-Zugangs |
   | `APP_PASSWORD_HASH` | Passwort-Hash für diesen Zugang (siehe unten) |
   | `SECRET_KEY` | Zufälliger Schlüssel zum Signieren der Sessions |
   | `IMPORT_SCAN_INTERVAL_SECONDS` | Wie oft (in Sekunden) der Import-Ordner geprüft wird (Standard 300) |

   Passwort-Hash erzeugen:

   ```bash
   python3 -c "from werkzeug.security import generate_password_hash as h; print(h('DEIN-PASSWORT'))"
   ```

   Zufälligen `SECRET_KEY` erzeugen:

   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```

   **Wichtig:** Der erzeugte Passwort-Hash enthält `$`-Zeichen
   (z.B. `scrypt:32768:8:1$abc$def...`). Docker Compose interpretiert
   einzelne `$` in `.env` als Variablenreferenz und schneidet den Wert
   sonst an dieser Stelle ab — jedes `$` im Hash muss daher durch `$$`
   ersetzt werden (z.B. `scrypt:32768:8:1$$abc$$def...`).

3. `.env` **niemals** committen — sie enthält Zugangsdaten und ist bereits
   über `.gitignore` ausgeschlossen.

## Starten

```bash
docker compose up -d --build
```

Startet zwei Container:
- `db` — PostgreSQL, legt beim allerersten Start automatisch das Datenbankschema an (`db/init.sql`)
- `web` — die Anwendung, erreichbar unter `http://localhost:8000`

Status/Logs prüfen:

```bash
docker compose ps
docker compose logs -f web
```

## Erstanmeldung & Benutzer anlegen

1. Mit `APP_USERNAME`/dem zu `APP_PASSWORD_HASH` gehörenden Klartext-Passwort
   unter `http://localhost:8000/login` anmelden. Dieser Zugang wirkt immer
   als Admin und bleibt dauerhaft als Notfall-Zugang bestehen, unabhängig
   von den unten beschriebenen Benutzerkonten.
2. Über den Navigationspunkt „Benutzerverwaltung“ echte Benutzerkonten
   anlegen. Drei Rollen stehen zur Wahl:

   | Rolle | Kann |
   |---|---|
   | **Standard** | Ist fest an eine Betriebsnummer gebunden, kein Betriebswechsel möglich |
   | **Erweitert** | Kann zwischen allen Betrieben wechseln |
   | **Admin** | Wie Erweitert, zusätzlich Zugriff auf die Benutzerverwaltung |

   Für jede Betriebsnummer, die im Alltag genutzt wird, sollte mindestens
   ein Standard-Benutzer angelegt werden. Passwörter können in der
   Benutzerverwaltung jederzeit durch einen Admin zurückgesetzt werden.

## Betriebs-Stammdaten pflegen

Der Notfall-Export liefert keine Adress-/Kontaktdaten der Betriebe. Für
den Ausdruck eines Auftrags (Abschnitt „Auftrag an“) sollten diese daher
einmalig gepflegt werden: Betriebsauswahl → „Bearbeiten“ → Firmenname,
Standortbezeichnung, Straße, PLZ/Ort, Telefon eintragen.

## Datenimport

- Das DMS legt täglich je Betrieb eine ZIP-Datei im Ordner `import/` ab,
  Dateiname im Format `JJJJMMTTHHMMSS_notfall.<Betriebsnummer>.zip`
  (Datenstand und Betriebsnummer werden daraus automatisch gelesen).
- Ein Hintergrundprozess prüft alle `IMPORT_SCAN_INTERVAL_SECONDS` Sekunden
  auf neue Dateien und importiert sie automatisch. Jeder Import ersetzt
  den kompletten vorherigen Datenstand des jeweiligen Betriebs (kein
  Verlauf), andere Betriebe bleiben dabei unberührt.
- Über „Import-Status“ in der Navigation lässt sich der Verlauf aller
  Importe einsehen und mit dem Button „Jetzt importieren“ ein sofortiger
  Scan auslösen, ohne auf das nächste Intervall zu warten.
- Erfolgreich verarbeitete ZIPs werden nach `import/processed/`
  verschoben. Schlägt der Import für dieselbe Datei dreimal hintereinander
  fehl, wird sie automatisch als `<Dateiname>.zip.failed` markiert und
  nicht weiter automatisch erneut versucht (Fehlermeldung dazu steht im
  Import-Status).

## Tägliche Nutzung

- **Suche** — Auftragssuche nach Auftragsnummer, Kundenname, Kennzeichen,
  Fahrgestellnummer oder Annahmedatum.
- **Auftragsdetail** — Kopfdaten, Positionen sowie ggf. Einlagerung/
  Ersatzfahrzeug zu einem Auftrag; Button „Drucken“ für eine dem
  Original-Auftragsdokument nachempfundene Druckansicht.
- **Teilebestand** — Suche im Ersatzteillager, optional über alle
  Niederlassungen hinweg (Checkbox).
- **Einlagerungen** / **Ersatzfahrzeuge** — eigene Listen-/Suchseiten,
  unabhängig davon, ob der zugehörige Auftrag noch im aktuellen
  DMS-Export enthalten ist.

## Betrieb & Wartung

```bash
docker compose logs -f web        # Logs der Web-Anwendung verfolgen
docker compose restart web        # Web-Container neu starten
docker compose down                # Container stoppen (Datenbank-Volume bleibt erhalten)
docker compose up -d --build web  # Nach Code-Änderungen: Image neu bauen und Container ersetzen
```

Die PostgreSQL-Daten liegen im benannten Docker-Volume `db_data` und
überstehen `docker compose down`/Neustarts. Für Backups empfiehlt sich ein
regelmäßiger Dump, z.B.:

```bash
docker compose exec db pg_dump -U notfall notfall > backup.sql
```

## Sicherheitshinweise

- `.env` enthält Zugangsdaten und darf nicht öffentlich geteilt oder
  eingecheckt werden.
- Der ENV-Notfall-Zugang sollte ein starkes, nur wenigen Personen
  bekanntes Passwort haben — er lässt sich nicht über die
  Benutzerverwaltung sperren oder löschen.
- Diese Anwendung hat keinen CSRF-Schutz und ist für den Betrieb in einem
  internen, abgesicherten Netzwerk gedacht, nicht für die Veröffentlichung
  im offenen Internet.

## Lizenz

Apache License 2.0, siehe `LICENSE`.
