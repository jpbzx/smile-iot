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
The **API** reads InfluxDB/PostgreSQL and publishes relay commands (`ON`/`OFF`/`RESET`)
to `smile-iot/command`; the browser never touches MQTT.

| Path | What it is |
|---|---|
| `backend/app.py` | Flask app factory (`python -m backend.app`, :5000) |
| `backend/config.py` | The only module that reads `.env` |
| `backend/api/` | Blueprints: auth, users, telemetry, control, system |
| `backend/services/` | postgres (auth/lockout/audit), influx (reads), mqtt_publisher, emailer |
| `backend/ingest/worker.py` | MQTT→InfluxDB worker (`python -m backend.ingest.worker`) |
| `backend/scripts/init_db.py` | One-time schema + seed admin |
| `frontend/` | Vite + React SPA (login, dashboard, profile, admin) |
| `docker-compose.yml` | mosquitto :1883 · postgres :5432 · influxdb :8086 |

## First-time setup

```bash
cd software
cp .env.example .env                      # then fill in generated secrets
docker compose up -d                      # broker + databases (influx auto-inits)
# create the scoped Influx token and paste it into .env (commands in .env.example)
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
