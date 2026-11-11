# Daily

A phone-friendly health log for a Raspberry Pi. Each person keeps their own days: six small meals, movement, weight, blood pressure, and how the day felt. Open it in the phone's browser. There is no app store install.

Built the same way as Dolf: one Python container, SQLite on a Docker volume, and a page served by that same container.

Daily listens on **port 8083**. The other apps already use 8000 (government-tracker), 8081 (math-facts and trip-planner), 8085 (wifi-monitor), 8088 (kinney-aviation), and 8092 (dolf-tracker).

## Quick start (Raspberry Pi or any Docker host)

```bash
git clone https://github.com/nibrocsolutions/health-tracker.git
cd health-tracker
docker compose up -d --build
```

On the phone, join the same Wi-Fi as the Pi and open `http://<pi-ip>:8083`.

Add it to the home screen (Safari: Share → Add to Home Screen, Chrome: menu → Add to Home screen) and it opens like an app.

### Useful commands

```bash
docker compose logs -f
git pull && docker compose up -d --build
docker compose down
```

`docker compose down` keeps the `health-data` volume. Add `-v` only when you mean to erase the logs.

## What you can do

- Keep a separate log for each person. This phone remembers who you picked
- Log six small meals. Each meal is a protein and a whole-food side, such as egg and cheese with fruit or a vegetable
- Add 30-minute sessions, cardio or weights, more than one on a day if you did both
- Write down weight, in pounds, on the days you want to
- Write down blood pressure, and pulse if you took it, on the days you want to
- Leave a feeling and a note for the day overall
- Open the calendar, move between months, and tap any day. The day opens under the month, and Log this day edits it
- Look at this week on Progress: meals, minutes, a weight trend, and recent blood pressure
- Rename or remove a person. Removing someone removes their days

The day is the date on the phone, not a clock on the Pi. Meals, workouts, and readings are stored in SQLite on the Pi, one database for everyone who uses that Pi. `docker compose down` keeps the data. `docker compose down -v` erases it.

Open `http://<pi-ip>:8083/admin` to export a full backup or replace the database from a backup file. There is no password on that page.

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
mkdir -p data
DATA_DIR=./data uvicorn app.main:app --reload --host 0.0.0.0 --port 8083
```

Tests:

```bash
pytest
```

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Health check |
| GET, POST | `/api/people` | People on this Pi |
| PATCH, DELETE | `/api/people/{id}` | Rename or remove a person and their days |
| GET | `/api/days?person_id=&start=&end=` | Calendar marks for a date range |
| GET, PUT | `/api/days/{person_id}/{date}` | One day: feeling, note, weight, blood pressure |
| PUT | `/api/days/{person_id}/{date}/meals` | All six meals |
| POST | `/api/days/{person_id}/{date}/workouts` | Add a cardio or weights session |
| DELETE | `/api/workouts/{id}` | Remove a session |
| GET | `/api/progress?person_id=&today=` | This week, recent weight, recent blood pressure |
| GET | `/api/admin/summary` | Counts for the admin page |
| GET | `/api/admin/export` | Full backup as JSON |
| POST | `/api/admin/import` | Replace the database from that backup |
| DELETE | `/api/admin/people/{id}` | Remove a person and their days |

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATA_DIR` | `./data` locally, `/data` in Docker | SQLite directory |
| `PORT` | `8083` | HTTP port |
| `DATABASE_URL` | `sqlite:///{DATA_DIR}/health.db` | Override the database |

## Notes

- Anyone who can open the address can read and change the logs, and anyone who can open `/admin` can export or replace the whole database. Keep it on your home network. Do not forward port 8083 to the internet.
- The phone has to reach the Pi. On the same Wi-Fi, use the Pi's address. Away from home, use a VPN you already trust. The page itself does not need a store account.
- The image is the multi-arch `python:3.12-slim` image, so it runs on a 64-bit Raspberry Pi and on a normal PC.

## Project layout

```
├── Dockerfile
├── docker-compose.yml
├── app/
│   ├── main.py
│   ├── api/routes.py
│   ├── models.py
│   ├── service.py
│   └── static/
└── tests/
```
