# Software

Flask API + MQTT ingest worker + React dashboard for the SMILE-IoT energy monitor.
Rebuilt from scratch 2026-07-09 (the previous Streamlit implementation lives in git
history and in [docs/SOFTWARE_ARCHITECTURE_2026-07-08.md](../docs/SOFTWARE_ARCHITECTURE_2026-07-08.md)).

> **Full as-built reference** (Docker, Flask internals, API map, DB schemas, MQTT, frontend):
> [docs/SOFTWARE_ARCHITECTURE_2026-07-09.md](../docs/SOFTWARE_ARCHITECTURE_2026-07-09.md)
> · Design history: [docs/BACKEND_REFACTOR_PLAN_2026-07-08.md](../docs/BACKEND_REFACTOR_PLAN_2026-07-08.md)

## Architecture

```text
ESP32 ⇄ Mosquitto ← ingest worker → InfluxDB ← Flask API ← React SPA (JWT)
        (docker)     (python proc)   (docker)      ↑ psycopg2
                                              PostgreSQL (docker)
```

The **ingest worker** subscribes to `smile-iot/power` 24/7 and batch-writes readings
to InfluxDB — telemetry is archived whether or not anyone has the dashboard open.
It also **derives** `power_W = current_A × grid voltage` and stores that voltage,
rather than trusting the firmware's values: the device has no voltage sensor, so grid
voltage is an admin-configurable setting (Postgres `app_settings`), editable from the
Admin page without reflashing. The **API** reads InfluxDB/PostgreSQL and publishes relay
commands (`ON`/`OFF`/`RESET`) to `smile-iot/command`; the browser never touches MQTT.

| Path | What it is |
|---|---|
| `backend/app.py` | Flask app factory (`python -m backend.app`, :5000) |
| `backend/config.py` | The only module that reads `.env` |
| `backend/api/` | Blueprints: auth, users, telemetry, control, settings, system |
| `backend/services/` | postgres (auth/lockout/audit), influx (reads), mqtt_publisher, emailer |
| `backend/ingest/worker.py` | MQTT→InfluxDB worker (`python -m backend.ingest.worker`) |
| `backend/scripts/init_db.py` | One-time schema + seed admin |
| `frontend/` | Vite + React SPA (login, dashboard, profile, admin) |
| `docker-compose.yml` | mosquitto :1883 · postgres :5432 · influxdb :8086 |

## First-time setup

Two kinds of local state get created that git never sees — a Python **virtual
environment** and a **secrets file**. Both are gitignored (`.venv/`, `.env` in
`.gitignore`) because they're specific to your machine, not the project:

| File/dir | Committed to git? | What it is |
|---|---|---|
| `.env.example` | Yes | Template listing every variable the app needs, with placeholder values (`generate-me`, `paste-scoped-token-here`). Safe to commit — no real secrets. |
| `.env` | **No** (gitignored) | Your actual config: real generated passwords + the Influx token. `backend/config.py` reads this at runtime. Created once by copying `.env.example`, then never shared or pushed. |
| `.venv/` | **No** (gitignored) | A Python virtual environment — an isolated copy of the Python interpreter + installed packages, local to this checkout. Keeps `backend/requirements.txt` deps off your system Python. Created by `python3 -m venv .venv`; safe to delete and recreate any time. |

If `.env` is ever missing, empty, or out of sync, just repeat the steps below —
nothing reads secrets from anywhere else.

```bash
cd software
cp .env.example .env                      # your machine's copy — fill in generated secrets next
docker compose up -d                      # broker + databases (influx auto-inits)
# generate each `generate-me` secret with:  python3 -c "import secrets; print(secrets.token_urlsafe(48))"
# then create the scoped Influx token and paste it into .env (commands in .env.example)
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
.venv/bin/python -m backend.scripts.init_db    # tables + admin/admin123 (change it!)
cd frontend && npm install
```

## Run (three terminals)

```bash
.venv/bin/python -m backend.ingest.worker   # 1 — telemetry archiver
.venv/bin/python -m backend.app             # 2 — API on :5000
cd frontend && npm run dev                  # 3 — dashboard on :5173
```

Login at http://localhost:5173 (seeded `admin` / `admin123`).

## Testing without hardware

```bash
# fake one firmware reading (exact contract shape):
docker exec smile_mosquitto mosquitto_pub -t smile-iot/power \
  -m '{"current_A":2.4,"power_W":552.0,"voltage_V":230.0,"outlet_state":"ON","trip_latched":false}'
# watch commands the dashboard sends:
docker exec smile_mosquitto mosquitto_sub -t smile-iot/command -v
```

`firmware/tools/mqtt_debug.py` does both interactively.

> **Firmware note:** boards flashed before 2026-07 still point at the public
> `broker.emqx.io`. Either reflash with `MQTT_BROKER` set to this machine's LAN IP
> (firmware/include/config.h) or set `MQTT_HOST=broker.emqx.io` in `.env` to bridge
> temporarily.
