# Hiking 🥾

Mehrbenutzer-Webapp zum Auswerten von GPX-Wandertracks (Quelle: App „Maps 3D"):
Statistiken, interaktive OpenStreetMap-Karten und Excel-Export – lauffähig lokal
oder als Docker-Container im Heimnetz.

## Features

- **GPX-Upload** (Multi-File) mit GPS-Filterung (Geschwindigkeits- und Zeitlücken-Filter)
- **Dashboard** mit Jahres-Übersicht und Gesamtsummen (Distanz, Höhenmeter, Dauer)
- **Interaktive Karten** (Folium/Leaflet):
  - Jahres-Karten – eingefärbt nach Monat, Layer-Steuerung pro Monat
  - Gesamt-Karte – eingefärbt nach Jahr, Tracks via Ramer-Douglas-Peucker vereinfacht
  - Klick auf einen Trail hebt die Tour hervor; Popup mit Datum, Distanz, Dauer, Ø-Tempo
  - **Doppelklick** auf Track, Datums-Label oder Startpunkt zoomt auf die komplette Tour
  - **Tour ausblenden** per 🗑-Button im Popup (Soft-Delete, siehe unten)
- **Excel-Export** der Wanderstatistik (`.xlsx`)
- **Login/Registrierung** (Flask-Login), benutzergetrennte Daten

### Soft-Delete von Touren

Der 🗑-Button im Karten-Popup blendet eine Tour aus, statt sie zu löschen: In der DB
wird `tour.is_hidden = True` gesetzt. Ausgeblendete Touren erscheinen danach **nirgends
mehr** – nicht auf Karten, nicht im Dashboard, nicht im Excel-Export. Die GPX-Datei
bleibt erhalten (Wiederherstellung über die DB möglich).

> Hinweis: Karten werden serverseitig zwischengespeichert (`map_cache`). Beim Ausblenden
> wird der Cache des betroffenen Jahres + die Gesamtkarte automatisch invalidiert und beim
> nächsten Aufruf neu erzeugt.

## Tech-Stack

Flask 3 · Flask-SQLAlchemy · Flask-Migrate (Alembic) · Flask-Login · Flask-WTF · Flask-Bcrypt
· Folium · openpyxl · SQLite · Gunicorn · Docker

## Projektstruktur

```
app/
  __init__.py        create_app() + CLI-Befehl create-admin
  config.py          Konfiguration (liest aus Umgebungsvariablen)
  models.py          User, Tour, MapCache
  auth/              Blueprint: register / login / logout
  main/              Blueprint: Dashboard, Upload, Karten, Export, Tour-Delete, Health
  gpx/
    parser.py        parse_gpx(), haversine()
    map_year.py      build_year_map() – Jahres-Karte
    map_all.py       build_all_map(), YEAR_COLORS – Gesamtkarte
    excel_export.py  generate_xlsx_for_user()
scripts/
  import_existing.py Einmal-Import bestehender GPX-Dateien
migrations/          Alembic-Migrationen
run.py               Lokaler Entry-Point (Port 5001)
Dockerfile, docker-compose.yml, Makefile
```

## Lokale Entwicklung

```bash
pip install -r requirements.txt

# .env anlegen (siehe Umgebungsvariablen)
flask db upgrade                       # Datenbank-Schema anwenden
export ADMIN_PASSWORD=...              # einmalig für create-admin
flask create-admin --username michael --email michael@example.com

python run.py                          # -> http://127.0.0.1:5001
```

## Umgebungsvariablen

| Variable         | Pflicht | Zweck                                                        |
|------------------|:------:|--------------------------------------------------------------|
| `SECRET_KEY`     | ✅     | Flask-Session-/CSRF-Schlüssel                                |
| `ADMIN_USERNAME` | (Docker)| Initialer Admin-Benutzer (Container-Start, `--if-none`)     |
| `ADMIN_EMAIL`    | (Docker)| E-Mail des initialen Admins                                 |
| `ADMIN_PASSWORD` | (Docker)| Passwort für `create-admin`                                 |
| `DATABASE_URL`   | –      | DB-URI (Default: SQLite unter `instance/hiking.db`)          |
| `USER_DATA_DIR`  | –      | Ablage für GPX-Dateien + generierte Karten (Default `user_data/`) |

Lokal liegen diese in `.env`, für Docker in `.env.docker` (beide sind in `.gitignore`
und `.dockerignore` und werden nicht ins Image gebacken).

## GPX-Import (bestehende Dateien)

```bash
python scripts/import_existing.py --username michael \
    --gpx-source /pfad/zu/Maps_3D
```
Idempotent: bereits vorhandene Dateinamen werden übersprungen. Nicht parsebare Dateien
werden gemeldet und ausgelassen.

## Docker-Deployment (Heim-Server)

Konfiguration im `Makefile` (Server `192.168.1.87`, Registry `192.168.1.87:5000`,
Deploy-Pfad `~/Docker_Images/hiking`).

```bash
make deploy     # Image bauen -> in Registry pushen -> compose+.env.docker rsyncen -> auf Server neu starten
make logs       # Live-Logs vom Server
make ps         # Container-Status
make restart    # Container neu starten
make up / down  # Container starten / stoppen
```

Die App läuft anschließend auf **http://192.168.1.87:8089** (Container-Port 8088 → Host 8089).

Beim Container-Start werden automatisch ausgeführt: `flask db upgrade` →
`flask create-admin --if-none` → Gunicorn (3 Worker). Migrationen werden also bei jedem
Deploy mit angewendet – kein manueller Schritt nötig.

### Persistente Volumes auf dem Server

| Host (`~/Docker_Images/hiking/`) | Container        | Inhalt                              |
|----------------------------------|------------------|-------------------------------------|
| `./data/`                        | `/app/data/`     | SQLite-Datenbank (`hiking.db`)      |
| `./user_data/`                   | `/app/user_data/`| GPX-Dateien + generierte Karten     |

### Neue Touren in den laufenden Container importieren

```bash
rsync -az /pfad/zu/neuen/gpx/ michael@192.168.1.87:~/temp_gpx/
ssh michael@192.168.1.87 "docker cp ~/temp_gpx/. hiking:/app/user_data/temp_import/"
ssh michael@192.168.1.87 "docker exec hiking python scripts/import_existing.py --username michael --gpx-source /app/user_data/temp_import"
ssh michael@192.168.1.87 "docker exec hiking rm -rf /app/user_data/temp_import && rm -rf ~/temp_gpx"
```

## Routen (Übersicht)

| Methode | Pfad                  | Zweck                                            |
|---------|-----------------------|--------------------------------------------------|
| GET     | `/`                   | Dashboard (Jahres-Grid + Summen)                 |
| GET/POST| `/upload`             | GPX-Upload (Multi-File)                          |
| GET     | `/map/year/<year>`    | Jahres-Karte (on-demand generiert, gecacht)      |
| GET     | `/map/all`            | Gesamtkarte (on-demand generiert, gecacht)       |
| GET     | `/export/xlsx`        | Excel-Download                                   |
| POST    | `/tour/<id>/delete`   | Tour ausblenden (Soft-Delete, antwortet `204`)   |
| GET     | `/health`             | Health-Check (ohne Login)                        |
| GET/POST| `/auth/register`      | Registrierung                                    |
| GET/POST| `/auth/login`         | Login                                            |
| GET     | `/auth/logout`        | Logout                                           |

## Datenbank-Schema

- **user**: `id, username, email, password_hash, created_at`
- **tour**: `id, user_id, filename, gpx_path, tour_date, distance_km, duration_min,
  avg_speed_kmh, ascent_m, descent_m, min_ele_m, max_ele_m, num_points, uploaded_at, is_hidden`
- **map_cache**: `id, user_id, map_type ('year'|'all'), year, html_path, generated_at`
