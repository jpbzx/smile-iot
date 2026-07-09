# SMILE-IoT — Software Directory Architecture Overview

> ⚠️ **SUPERSEDED (2026-07-09).** This document describes the **retired Streamlit
> stack**, torn down and replaced by the Flask + React rebuild. It stays as the
> historical record of what existed and why it was replaced. The current reference
> is [SOFTWARE_ARCHITECTURE_2026-07-09.md](SOFTWARE_ARCHITECTURE_2026-07-09.md).

**Date:** 2026-07-08
**Scope:** `software/` as it exists today (Streamlit-based backend), its structure, runtime
model, data stores, and its integration contract with the ESP32 firmware.
**Companion doc:** [BACKEND_REFACTOR_PLAN_2026-07-08.md](BACKEND_REFACTOR_PLAN_2026-07-08.md)
— the plan to replace this with Flask + React.

---

## 1. System context

```text
                 (1 Hz telemetry, JSON)                    (reads/writes)
┌─────────┐  smile-iot/power   ┌──────────────┐   MQTT    ┌────────────────────────┐
│  ESP32  ├───────────────────►│ MQTT broker  ├──────────►│ software/ (this layer) │
│ firmware│◄───────────────────┤ broker.emqx. │◄──────────┤  Streamlit app         │
└─────────┘  smile-iot/command │ io (public!) │           │  ├─ per-session MQTT   │
   ON/OFF/RESET (plain text)   └──────────────┘           │  │  subscriber thread  │
                                                          │  ├─ PostgreSQL (users) │
                                                          │  └─ InfluxDB (series)  │
                                                          └───────────┬────────────┘
                                                                      │ HTTP :8501
                                                                ┌─────▼─────┐
                                                                │  Browser  │
                                                                └───────────┘
```

Three trust/runtime domains:

1. **Edge** — ESP32 running FreeRTOS firmware (`firmware/`). Samples the SCT-013 current
   clamp, computes RMS current and power, drives the outlet relay, enforces a local
   overcurrent cutoff (trip latch). Publishes telemetry and obeys relay commands.
2. **Transport** — a public MQTT broker (`broker.emqx.io:1883`). No private broker is
   deployed; anyone on the internet can read telemetry or publish commands.
3. **Application** — everything in `software/`: a Streamlit web app that authenticates
   users (PostgreSQL), subscribes to telemetry, renders dashboards, forwards relay
   commands, and archives readings (InfluxDB).

---

## 2. Directory map — where, how, why

```text
software/
├── app.py                  # Entrypoint: streamlit run app.py
│                           #   Session bootstrap, 30-min inactivity timeout,
│                           #   role-based page navigation (admin vs user).
├── views/                  # One file per Streamlit page (st.Page / st.navigation)
│   ├── login.py            #   Login form + password-reset request/confirm flows
│   ├── dashboard.py        #   The main UI: broker connect controls, KPIs, charts,
│   │                       #   outlet ON/OFF buttons, auto-refresh loop
│   ├── admin_panel.py      #   Create users. Device management is a TODO stub.
│   └── profile.py          #   Change own password
├── db/
│   ├── postgres_manager.py #   All user/auth SQL: login verify (bcrypt), failed-
│   │                       #   attempt lockout, audit log, reset tokens, add_user,
│   │                       #   update_password, init_db() schema creation
│   └── influx_manager.py   #   InfluxDBManager.save_energy_reading() — write-only;
│                           #   there is NO read path (history views are placeholders)
├── utils/
│   ├── mqtt_client.py      #   paho-mqtt subscriber + thread→Streamlit bridge +
│   │                       #   publish_command(); also triggers Influx writes
│   ├── emailer.py          #   SMTP password-reset mail (env-configured)
│   ├── simulated_data.py   #   Constants (GRID_VOLTAGE, COST_PER_KWH, buffer size)
│   │                       #   + synthetic data generators (demo/testing)
│   └── database.py         #   EMPTY — dead file
├── docker-compose.yml      # postgres:15 (:5432) + influxdb:2.7 (:8086). No broker,
│                           # no app service in the CURRENT file — but see note below:
│                           # a leftover `smile_dashboard` container from an older
│                           # compose revision may still be serving :8501.
├── .env                    # Credentials & config (gitignored). NOTE: DB_HOST is set
│                           # to the Docker service name, wrong for host-run app.
├── data/                   # Docker volume mounts (gitignored)
├── requirements.txt        # Unpinned deps
└── software_README.md      # Per-directory README
```

**Why this shape:** the project grew from a single-file Streamlit prototype. Streamlit
was chosen so the same Python process could be UI + MQTT consumer + DB writer with no
API layer. `views/` split out when multipage navigation and RBAC arrived; `db/` and
`utils/` split business logic from UI so the paho callbacks (which must not touch
Streamlit APIs) could live outside page scripts.

---

## 3. Runtime model (the important part)

Streamlit reruns the active page script top-to-bottom on every interaction. That shapes
everything:

1. **Auth gate** — [app.py](../software/app.py) checks `st.session_state.logged_in` and
   an inactivity timestamp (`SESSION_TIMEOUT_MIN`, default 30 min). Unauthenticated
   sessions only get the login page. Role `admin` additionally unlocks the admin panel.
   Every protected view re-checks the flag itself (defense in depth, since views are
   directly addressable).

2. **MQTT ingestion is session-bound** — clicking *Connect* in the dashboard sidebar
   creates a paho client (`utils/mqtt_client.py`). paho callbacks run on a background
   thread where Streamlit state is unusable, so messages land in a **module-level
   `queue.Queue`**; `sync_mqtt()` drains it into `st.session_state.mqtt_messages` at the
   top of each rerun. Buffer is capped at `MAX_BUFFER_SIZE = 120` messages.

   > Consequence: telemetry is only ingested (and only archived to InfluxDB) **while a
   > browser tab is open, logged in, and connected**. Close the tab → data loss. This is
   > the single biggest architectural weakness and the core motivation for the refactor.

3. **InfluxDB archiving rides the callback** — `_on_message()` synchronously writes each
   reading via `influx_db.save_energy_reading()` (SYNCHRONOUS write API). A slow/down
   InfluxDB stalls the MQTT network loop.

4. **Commands** — dashboard buttons call `publish_command()` on the same paho client,
   publishing plain-text `ON`/`OFF` to the command topic (QoS 1). The `RESET` trip-clear
   command exists in firmware but has **no UI**.

5. **Auto-refresh** — the dashboard ends with a `time.sleep(1)` countdown loop and
   `st.rerun()`, holding a server thread per session for the whole interval.

---

## 4. Data stores

### PostgreSQL (`smile_postgres`, users & control-plane) — schema from `init_db()`

| Table | Purpose | Notes |
|---|---|---|
| `utilizadores` | Users: `username`, `email`, bcrypt `password_hash`, `role` (`admin`/`user`), `failed_attempts`, `locked_until` | Lockout after 5 failures for 15 min (env-tunable) |
| `dispositivos` | ESP32 boards: `mac_address`, display name, `limite_corrente` | **Created but unused** — no code reads/writes it |
| `acessos_dispositivos` | user↔device permission join table | **Created but unused** |
| `login_logs` | Audit: every attempt with success flag + reason | Written by `verify_login()` |
| `password_reset_tokens` | Single-use, 60-min expiry, `used` flag | `secrets.token_urlsafe(32)` |

`init_db()` also seeds `admin`/`admin123`. **It only runs manually**
(`python -m db.postgres_manager` from `software/`) — a fresh `docker compose up` has no
tables until someone remembers this step.

### InfluxDB (`smile_influx`, org `smile_org`, bucket `energy_data`)

Measurement **`energy_reading`**:

| Kind | Name | Values |
|---|---|---|
| tag | `device` | hardcoded `"SCT-013_ESP32"` |
| tag | `outlet_state` | `"ON"` / `"OFF"` / `"UNKNOWN"` |
| field | `current_A` | float |
| field | `power_W` | float |
| field | `voltage_V` | float (always 230.0 — nominal, no voltage sensing hardware) |

`trip_latched` from the firmware payload is **dropped**, and nothing ever **reads** the
bucket — the dashboard's daily energy/cost panel is a zeroed placeholder.

---

## 5. Firmware integration — the MQTT contract

Single source of truth: [firmware/include/config.h](../firmware/include/config.h) and
[firmware/src/network_task.cpp](../firmware/src/network_task.cpp).

**Broker:** `broker.emqx.io:1883` (public; the firmware's MQTT username/password are
accepted but meaningless there). Firmware client id: `esp32-1-<MAC>`.

### Telemetry — topic `smile-iot/power`, published every 1 s (`SENSOR_PERIOD_MS = 1000`)

```json
{"current_A": 2.412, "power_W": 554.8, "voltage_V": 230.0,
 "outlet_state": "ON", "trip_latched": false}
```

| Field | Type | Producer detail | Consumer today |
|---|---|---|---|
| `current_A` | float, 3 dp | RMS over 1000 ADC samples, CT calib 30 A/V | KPI + chart |
| `power_W` | float, 1 dp | `current_A × 230 V` (computed on-device) | **Ignored** — dashboard recomputes it |
| `voltage_V` | float | Constant 230.0 (nominal) | Stored to Influx only |
| `outlet_state` | `"ON"`/`"OFF"` | Relay state | Status text |
| `trip_latched` | bool | Overcurrent cutoff latched (>15 A) | **Ignored entirely** |

### Commands — topic `smile-iot/command`, plain text (not JSON)

| Payload | Firmware action | UI today |
|---|---|---|
| `ON` | Close relay (refused while trip latched) | Button |
| `OFF` | Open relay | Button |
| `RESET` | Clear overcurrent trip latch | **None** (only `firmware/tools/mqtt_debug.py`) |

The dashboard derives the command topic by string-replacing `power` → `command` in the
telemetry topic, so it follows whatever topic the sidebar sets.

**Test harness:** `firmware/tools/mqtt_debug.py` (own venv) prints telemetry and
publishes commands interactively — useful for exercising either side without hardware.

---

## 6. Configuration

`.env` in `software/` (gitignored, loaded by `postgres_manager` via python-dotenv):

| Group | Vars | Read by |
|---|---|---|
| Postgres | `POSTGRES_USER/PASSWORD/DB` (container init), `DB_HOST/PORT/NAME/USER/PASSWORD` (app) | docker-compose; `postgres_manager` |
| InfluxDB | `INFLUX_USER/PASSWORD/ORG/BUCKET/ADMIN_TOKEN` | docker-compose **only** — `influx_manager.py` ignores env and hardcodes url/token/org/bucket |
| Auth policy | `MAX_FAILED_ATTEMPTS`, `LOCKOUT_MINUTES`, `SESSION_TIMEOUT_MIN` | `postgres_manager`, `app.py` |
| SMTP | `SMTP_HOST/PORT/USER/PASSWORD`, `RESET_URL_BASE` | `emailer.py` |

Two known config landmines:

- `DB_HOST=postgres_db` in `.env` is the **Docker service name**; the Streamlit app runs
  on the host and needs `localhost`. dotenv overrides the code default, so login breaks
  until this is edited.
- The **InfluxDB admin token is hardcoded in `db/influx_manager.py` and committed to git
  history** — must be rotated regardless of the refactor.

---

> **Live-environment note (found 2026-07-08):** an earlier revision of
> docker-compose.yml *did* have a `streamlit_app` service; its container
> (`smile_dashboard`, image `software-streamlit_app`, built ~6 weeks ago) survived the
> compose-file change and still runs the dashboard on :8501 with the old environment
> baked in. Inside that container `DB_HOST=postgres_db` is correct (Docker network),
> which explains the `.env` value. Host-run instructions below need
> `DB_HOST=localhost`. The leftover container also embeds the hardcoded Influx token in
> its image — one more reason rotation (refactor Phase 0) matters.

## 7. How to run it today

```bash
cd software
docker compose up -d                 # postgres + influxdb (first run: influx auto-setup)
# edit .env: DB_HOST=localhost
source .venv/bin/activate
python -m db.postgres_manager        # one-time: create tables + admin/admin123
streamlit run app.py                 # http://localhost:8501
# In the dashboard sidebar: Connect to broker.emqx.io / smile-iot/power
```

---

## 8. Known issues & limitations (verified 2026-07-08)

| # | Severity | Issue | Where |
|---|---|---|---|
| 1 | Critical | InfluxDB admin token hardcoded & committed | `db/influx_manager.py:14` |
| 2 | Critical | `.env` `DB_HOST=postgres_db` breaks host-run app | `.env` |
| 3 | Critical | Ingestion only while a dashboard session is open → data loss | design (`utils/mqtt_client.py`) |
| 4 | High | Public broker, unauthenticated relay control from anywhere | `views/dashboard.py:77`, firmware `config.h` |
| 5 | High | Sync Influx write inside MQTT callback can stall the loop | `utils/mqtt_client.py:75` |
| 6 | High | `init_db()` never runs automatically | `db/postgres_manager.py:294` |
| 7 | High | No Influx read path; history panel is fake zeros | `views/dashboard.py:37,138` |
| 8 | Med | `trip_latched` never surfaced; no RESET UI | dashboard |
| 9 | Med | "Real time window" slices last N *messages*, not minutes (1 Hz ⇒ "60 min" ≈ 60 s; buffer caps at 120 msgs ≈ 2 min) | `views/dashboard.py:121` |
| 10 | Med | Dashboard recomputes power, ignoring firmware's `power_W` | `views/dashboard.py:132` |
| 11 | Med | Change-password doesn't ask for the current password | `views/profile.py` |
| 12 | Low | Stale README (describes nonexistent `listener.py`/`data.json`); empty `utils/database.py`; unpinned deps; `.venv/` in tree; mixed PT/EN | misc |

Items 3, 4, 5, 7 are *architectural* — they are what the Flask + React refactor is
designed to eliminate, not patch. See the companion refactor plan.
