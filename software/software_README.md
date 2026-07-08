# Software

Python application layer: authentication, live energy dashboard, telemetry archiving.

> **Docs:**
> - Current architecture, directory map, firmware/MQTT contract, known issues →
>   [docs/SOFTWARE_ARCHITECTURE_2026-07-08.md](../docs/SOFTWARE_ARCHITECTURE_2026-07-08.md)
> - Planned Flask + React rewrite (endpoint map, phases) →
>   [docs/BACKEND_REFACTOR_PLAN_2026-07-08.md](../docs/BACKEND_REFACTOR_PLAN_2026-07-08.md)

## What's here (today: Streamlit implementation)

| Path | Role |
|---|---|
| `app.py` | Entrypoint — session, timeout, role-based navigation |
| `views/` | Pages: login, dashboard, admin panel, profile |
| `db/postgres_manager.py` | Users/auth SQL (bcrypt, lockout, audit, reset tokens) + `init_db()` |
| `db/influx_manager.py` | InfluxDB writes (energy readings) |
| `utils/mqtt_client.py` | MQTT subscriber ↔ Streamlit bridge, command publishing |
| `utils/emailer.py` | SMTP password-reset mail |
| `docker-compose.yml` | PostgreSQL 15 (:5432) + InfluxDB 2.7 (:8086) |

## Run

```bash
cd software
docker compose up -d              # databases
# edit .env: DB_HOST=localhost   (app runs on the host, not in Docker)
source .venv/bin/activate         # or create: python3 -m venv .venv && pip install -r requirements.txt
python -m db.postgres_manager     # ONE-TIME: create tables + admin user (admin/admin123)
streamlit run app.py              # http://localhost:8501
```

In the dashboard sidebar, connect to the broker (`broker.emqx.io`, topic
`smile-iot/power`). To exercise without hardware: `firmware/tools/mqtt_debug.py`.

> ⚠️ This implementation only ingests telemetry while a logged-in dashboard tab is
> connected — see the architecture doc's known-issues list. The Flask + React refactor
> plan addresses this.
