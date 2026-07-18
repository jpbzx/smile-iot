# SMILE-IoT Software Architecture — As Built (Flask + React)

**Date:** 2026-07-09 · **Branch:** `feature/flask-react-backend`
**Status:** current — this is the reference for the stack that exists today.
**Supersedes:** [SOFTWARE_ARCHITECTURE_2026-07-08.md](SOFTWARE_ARCHITECTURE_2026-07-08.md)
(the retired Streamlit stack). Design intent and endpoint contract were specified in
[BACKEND_REFACTOR_PLAN_2026-07-08.md](BACKEND_REFACTOR_PLAN_2026-07-08.md); this
document describes what was actually built, how, and why.

---

## 1. The system in one picture

```text
                    1 Hz JSON telemetry                      batched writes
┌─────────┐  smile-iot/power   ┌────────────┐  subscribe  ┌───────────────┐        ┌──────────┐
│  ESP32  ├───────────────────►│ Mosquitto  ├────────────►│ ingest worker ├───────►│ InfluxDB │
│ firmware│◄───────────────────┤ (Docker)   │             │ (host, py)    │        │ (Docker) │
└─────────┘  smile-iot/command └─────▲──────┘             └───────────────┘        └────▲─────┘
             ON / OFF / RESET        │ publish (QoS 1)                                  │ Flux
                                     │                                                  │ reads
                              ┌──────┴──────────────────────────────────────────────────┴──┐
                              │                Flask API — host, :5000                     │
                              │   /api/auth   /api/users   /api/telemetry   /api/control   │
                              │   /api/health /api/system/status /api/admin/login-logs     │
                              └──────▲──────────────────────────────────┬──────────────────┘
                                     │ JSON + JWT (Bearer)              │ psycopg2
                              ┌──────┴──────┐                    ┌──────▼───────┐
                              │  React SPA  │                    │  PostgreSQL  │
                              │ Vite, :5173 │                    │   (Docker)   │
                              └─────────────┘                    └──────────────┘
```

### Design principles (each one fixes a documented flaw of the old stack)

| Principle | What it means | Old-stack flaw it kills |
|---|---|---|
| **Ingestion is a service, not a side effect** | `backend/ingest/worker.py` runs 24/7 regardless of who's logged in | Telemetry was only archived while a dashboard tab was open |
| **The database is the interface** | Worker and API share zero memory; "latest reading" = newest InfluxDB point | Fragile thread-bridge between paho callbacks and UI state |
| **The browser speaks HTTP only** | All MQTT lives server-side; the SPA calls REST endpoints | Browser sessions each owned a broker connection and could pick any broker |
| **One config source** | Only `backend/config.py` reads `.env`; everything imports from it | Hardcoded credentials (the committed InfluxDB token) |
| **Functional first** | No ORM, no WebSockets, no queue, no cache — two small processes + a static SPA | Complexity without need |

---

## 2. Directory map

```text
software/
├── docker-compose.yml        # infra: mosquitto + postgres + influxdb (§3)
├── mosquitto/mosquitto.conf  # broker config (§3.2)
├── .env                      # secrets/config — gitignored, never committed
├── .env.example              # committed template + token-creation recipe (§4)
├── backend/
│   ├── app.py                # Flask app factory + dev entrypoint (§5)
│   ├── config.py             # THE .env reader (§4)
│   ├── requirements.txt      # pinned (compatible-release) deps
│   ├── api/                  # HTTP layer — one blueprint per resource (§5.2, §6)
│   │   ├── helpers.py        #   err() + @admin_required
│   │   ├── auth.py           #   login / me / password-reset
│   │   ├── users.py          #   admin CRUD + self password change
│   │   ├── telemetry.py      #   latest / range / daily (Influx reads)
│   │   ├── control.py        #   outlet ON-OFF + reset-trip (MQTT publish)
│   │   └── system.py         #   health, stack status, login audit log
│   ├── services/             # business/persistence layer, no Flask imports
│   │   ├── postgres.py       #   auth, lockout, audit, users, reset tokens (§7)
│   │   ├── influx.py         #   the three Flux read queries (§8)
│   │   ├── mqtt_publisher.py #   lazy singleton command publisher (§9.3)
│   │   └── emailer.py        #   SMTP reset mail (disabled when unconfigured)
│   ├── ingest/worker.py      # the MQTT→InfluxDB archiver process (§9.2)
│   └── scripts/init_db.py    # idempotent schema + admin seed (§7.3)
└── frontend/                 # Vite + React SPA (§10)
    ├── vite.config.js        #   dev server + /api proxy → :5000
    └── src/
        ├── api/client.js     #   fetch wrapper: JWT header, errors, 401 handling
        ├── auth/AuthContext.jsx
        ├── hooks/usePolling.js
        ├── theme.js          #   validated chart palette, light+dark
        ├── App.jsx           #   routes + guards + topbar layout
        ├── pages/            #   Login, Dashboard, Profile, Admin
        └── components/EnergyCharts.jsx  # Power/Current/Daily charts (Recharts)
```

---

## 3. Infrastructure — how Docker is implemented

Docker Compose runs **infrastructure only**. The Python processes and the Vite dev
server run on the host during development (simplest debug loop); containerizing them
is deferred work (§14). All state lives in bind mounts under `software/data/`
(gitignored), so `rm -rf data/` + `docker compose up -d` is a full factory reset.

### 3.1 Services

| Service | Image | Container | Port | Volume | Healthcheck |
|---|---|---|---|---|---|
| `mosquitto` | `eclipse-mosquitto:2` | `smile_mosquitto` | 1883 | `./data/mosquitto` | `mosquitto_sub -t '$SYS/#' -C 1` |
| `postgres` | `postgres:15` | `smile_postgres` | 5432 | `./data/postgres` | `pg_isready` |
| `influxdb` | `influxdb:2.7` | `smile_influx` | 8086 | `./data/influx` | `influx ping` |

All three have `restart: always` — they survive reboots; only the host processes
need manual starting.

### 3.2 Mosquitto (the broker the public emqx used to be)

`mosquitto/mosquitto.conf`:

```conf
listener 1883
allow_anonymous true          # acceptable on a trusted LAN for the prototype
persistence true              # QoS-1 queues survive broker restarts
persistence_location /mosquitto/data/
log_dest stdout               # docker logs smile_mosquitto
```

Running our own broker removes the old stack's worst exposure: on public
`broker.emqx.io`, anyone on the internet could publish `ON` to the relay. Anonymous
access *inside the LAN* is a documented, accepted trade-off (§12); `password_file` +
per-topic ACLs are the upgrade path.

### 3.3 InfluxDB first-boot initialization

The `DOCKER_INFLUXDB_INIT_*` environment variables (from `.env`) make the container
self-provision **on first run only** (empty volume): it creates the org
(`smile_org`), the bucket (`energy_data`, infinite retention), the admin user, and
the admin token. On every later start they're ignored.

The backend does **not** use that admin token. A scoped token is created once and
pasted into `.env` as `INFLUX_TOKEN`:

```bash
docker exec smile_influx influx bucket list --org smile_org --name energy_data  # → bucket id
docker exec smile_influx influx auth create --org smile_org \
  --read-bucket <id> --write-bucket <id> --description "smile-backend"
```

Least privilege: if that token ever leaks, it can read/write one bucket — it cannot
administer users, tokens, or other buckets. (The old stack's committed admin token
died with the wiped instance; rotation-by-teardown.)

### 3.4 PostgreSQL

Plain `postgres:15` with credentials from `.env` (`POSTGRES_USER=smile`,
`POSTGRES_DB=smile_iot`). Schema creation is *not* the container's job — it belongs
to `backend/scripts/init_db.py` (§7.3) so it's versioned with the code that uses it.

---

## 4. Configuration — one reader, one file

`backend/config.py` loads `software/.env` at import time and exposes typed
constants. **No other module touches `os.environ`.** The full surface:

| Group | Variables | Consumed by |
|---|---|---|
| Postgres | `POSTGRES_USER/PASSWORD/DB`, `DB_HOST/PORT` | compose (container init) + `services/postgres` |
| InfluxDB | `INFLUX_USER/PASSWORD/ORG/BUCKET/ADMIN_TOKEN` (init), `INFLUX_URL`, `INFLUX_TOKEN` (scoped) | compose init · backend reads/writes |
| MQTT | `MQTT_HOST/PORT`, `MQTT_TOPIC_TELEMETRY/COMMAND` | worker + publisher |
| API | `JWT_SECRET_KEY`, `SESSION_TIMEOUT_MIN=30`, `COST_PER_KWH=0.25` | app factory, JWT, daily-cost query |
| Login policy | `MAX_FAILED_ATTEMPTS=5`, `LOCKOUT_MINUTES=15` | lockout logic |
| SMTP | `SMTP_HOST/PORT/USER/PASSWORD`, `RESET_URL_BASE` | emailer (empty host ⇒ sending disabled) |

`.env` is gitignored; `.env.example` is the committed template and contains the
token-creation recipe. `MQTT_HOST=broker.emqx.io` is the documented bridge for
boards that haven't been reflashed to the LAN broker yet.

---

## 5. The Flask application — how it's set up

### 5.1 App factory

`backend/app.py` exposes `create_app()` (standard Flask factory pattern — testable,
no import-time side effects) and refuses to boot without `JWT_SECRET_KEY`. Dev run:
`python -m backend.app` → `127.0.0.1:5000`, debug reloader on.

Inside the factory, in order:

1. **JWT** — `flask-jwt-extended`. Access tokens carry `sub` = user id (string),
   plus custom claims `role` and `username`; expiry = `SESSION_TIMEOUT_MIN` (30 min,
   same session length the old app enforced). No refresh tokens: on expiry the SPA
   drops to the login page (accepted for a LAN prototype).
2. **CORS** — allowed origin `http://localhost:5173`. In practice dev traffic is
   same-origin because Vite proxies `/api` (§10.1); CORS is belt-and-braces.
3. **Uniform errors** — three JWT loaders (missing/invalid/expired) plus 404/405/500
   handlers all return the same shape: `{"error": "<code>", "message": "<human>"}`.
   Every endpoint uses `api/helpers.py:err()` for the same reason: **the frontend
   has exactly one error format to parse.**
4. **Blueprints** — one per resource, mounted under `/api`:

| Blueprint | Prefix | File |
|---|---|---|
| system | `/api` | `api/system.py` (health, status, login-logs) |
| auth | `/api/auth` | `api/auth.py` |
| users | `/api/users` | `api/users.py` |
| telemetry | `/api/telemetry` | `api/telemetry.py` |
| control | `/api/control` | `api/control.py` |

### 5.2 Authorization model

Two gates, both in `api/helpers.py` / `flask-jwt-extended`:

- `@jwt_required()` — any valid token (dashboard, profile, control endpoints).
- `@admin_required` — wraps JWT verification, then checks the `role` claim; non-admins
  get `403 forbidden`. Used by user management and the audit log.

Role lives **in the token**, so no DB hit per request for authorization. The
worst-case staleness (a demoted admin keeps admin claims until the token expires)
is bounded by the 30-minute TTL — fine at this scale.

### 5.3 Anatomy of a request

```text
POST /api/auth/login {"username","password"}
  └─ services/postgres.verify_login()
       ├─ locked?           → raise AccountLocked        → 423 + locked_until
       ├─ bcrypt mismatch   → failed_attempts++ (→ lock) → 401
       └─ match             → counters reset, audit row  → 200 + JWT
Subsequent calls: Authorization: Bearer <jwt>
  └─ blueprint → service → Postgres/Influx/MQTT → JSON out
```

---

## 6. API map — as built and verified

Conventions: JSON bodies; `Authorization: Bearer <token>` unless *public*; errors
are `{"error","message"}`; timestamps ISO-8601 UTC. Everything below returned the
listed codes in the 2026-07-08/09 verification run (§13).

### Auth

| Endpoint | Auth | Body → Success | Errors |
|---|---|---|---|
| `POST /api/auth/login` | public | `{username,password}` → `200 {access_token, user:{id,username,role}}` | `400` missing fields · `401 invalid_credentials` (same for unknown user — no enumeration) · `423 account_locked` + `locked_until` |
| `GET /api/auth/me` | bearer | → `200 {id,username,email,role}` | `401` (also when the token's user was deleted) |
| `POST /api/auth/password-reset/request` | public | `{email}` → **always** `202` neutral message | `429 too_many_requests` (60 s per-email cooldown) |
| `POST /api/auth/password-reset/confirm` | public | `{token,new_password}` → `200 password_updated` | `400 invalid_token \| token_used \| token_expired \| weak_password` |

With SMTP unconfigured the reset token is logged to the API console (dev
convenience, documented; the HTTP response never leaks it).

### Users

| Endpoint | Auth | Body → Success | Errors |
|---|---|---|---|
| `GET /api/users` | admin | → `200 [{id,username,email,role,locked_until,created_at}]` | `401/403` |
| `POST /api/users` | admin | `{username≥3,email(@),password≥5,role}` → `201 {id}` | `400 validation` · `409 duplicate` |
| `PATCH /api/users/{id}` | admin | `{role}` → `200` | `400` · `404` |
| `DELETE /api/users/{id}` | admin | → `204` | `404` · `409 cannot_delete_self` |
| `PUT /api/users/me/password` | bearer | `{current_password,new_password}` → `200` | `403 wrong_current_password` · `400 weak_password` |

Requiring the current password is an intentional hardening over the old app.

### Telemetry (reads InfluxDB only)

| Endpoint | Auth | Params → Success | Notes |
|---|---|---|---|
| `GET /api/telemetry/latest` | bearer | → `200 {timestamp,current_A,power_W,voltage_V,outlet_state,trip_latched}` or `204` | `204` = no point in 5 min = device offline |
| `GET /api/telemetry/range` | bearer | `minutes` (1–1440, def 60), `every` (`^\d+[smh]$`, def `10s`) → `200 {points:[{t,current_A,power_W}]}` | downsampled via `aggregateWindow(mean)` |
| `GET /api/telemetry/daily` | bearer | `days` (1–365, def 30) → `200 {days:[{date,energy_kWh,cost_eur}]}` | cost = kWh × `COST_PER_KWH` |

### Control (publishes MQTT — the firmware contract verbatim)

| Endpoint | Auth | Body → Success | Errors |
|---|---|---|---|
| `POST /api/control/outlet` | bearer | `{state:"ON"\|"OFF"}` → `202 {published:true}` | `400 invalid_state` · `503 broker_unavailable` |
| `POST /api/control/reset-trip` | bearer | → `202 {published:true}` | `503 broker_unavailable` |

**Why 202:** publishing ≠ the relay switched. The board acts and *confirms through
telemetry* — the UI watches `outlet_state`/`trip_latched` flip in `/latest` (~2 s).

### System & audit

| Endpoint | Auth | Success |
|---|---|---|
| `GET /api/health` | public | `200 {status:"ok"}` (liveness) |
| `GET /api/system/status` | bearer | `200 {postgres_ok, influx_ok, mqtt_connected, last_reading_age_s}` |
| `GET /api/admin/login-logs?limit=` | admin | `200 {logs:[{username,success,reason,timestamp}]}` (limit 1–1000) |

`mqtt_connected` actively connects the lazy publisher if needed, so it reports
broker *reachability*, not merely "has anyone pressed a button yet".

---

## 7. PostgreSQL — users, auth, audit

### 7.1 Schema (from `services/postgres.py:init_db`)

| Table | Columns (key ones) | Purpose |
|---|---|---|
| `users` | `username` UNIQUE, `email` UNIQUE, `password_hash` (bcrypt), `role` CHECK(admin\|user), `failed_attempts`, `locked_until TIMESTAMPTZ`, `created_at` | Accounts + lockout state |
| `login_logs` | `username`, `success`, `reason`, `at TIMESTAMPTZ` | Audit trail of every attempt (`success`, `invalid_password`, `locked`, `locked_after_5`, `no_such_user`) |
| `password_reset_tokens` | `token` UNIQUE, `user_id` FK CASCADE, `expires_at`, `used` | Single-use, 60-min tokens (`secrets.token_urlsafe(32)`) |
| `devices` | `mac_address` UNIQUE, `name`, `current_limit_a` | **Phase-5 ready, unused** in single-board scope |
| `device_access` | (`user_id`,`device_id`) PK, both FK CASCADE | **Phase-5 ready, unused** |

Design choices: English names (the rebuild wiped all data, so the old Portuguese
schema imposed no migration constraint); `TIMESTAMPTZ` everywhere with
timezone-aware `datetime.now(timezone.utc)` in code (the old stack mixed naive
`utcnow()` with `TIMESTAMP`).

### 7.2 The lockout algorithm (ported behaviour, verified)

1. Wrong password → `failed_attempts + 1` atomically (`UPDATE … RETURNING`).
2. Counter hits `MAX_FAILED_ATTEMPTS` (5) → `locked_until = now + 15 min`; the
   login response is `423` with that timestamp **even for the correct password**.
3. Successful login or completed password reset → counter and lock cleared.
4. Every step writes `login_logs` — and auditing is wrapped so it can never break
   the login path itself.

### 7.3 Bootstrap

`python -m backend.scripts.init_db` — idempotent (`CREATE TABLE IF NOT EXISTS`),
seeds `admin`/`admin123` **only when the users table is empty**, and prints a
change-it warning. Connections are context-managed (`get_conn()` commits on
success, rolls back on exception, always closes) — no leaked cursors, unlike the
old manager's early-return paths.

---

## 8. InfluxDB — the energy time series

### 8.1 Point shape (written by the worker)

```text
measurement: energy_reading
tag:    device        = payload "mac" if present, else "SCT-013_ESP32"
fields: current_A     float      power_W  float      voltage_V float
        outlet_state  string     trip_latched  int (0/1)
time:   explicit nanosecond timestamp, set at receive
```

Two deliberate choices:

- **`outlet_state`/`trip_latched` are fields, not tags.** Tags create one series
  per value combination; as fields there is exactly one series per device, so the
  read side is `last()` + `pivot()` → a single row with every field at the same
  timestamp. It also keeps series cardinality flat.
- **Explicit timestamps.** Points without a time get server-assigned times at
  write; inside a 50-point batch those can collide and **silently overwrite** each
  other (same measurement+tags+time = same point). `time.time_ns()` at receive
  makes every 1 Hz reading distinct.

### 8.2 The three read queries (`services/influx.py`)

*Latest* — liveness-bounded snapshot:
```flux
from(bucket:"energy_data") |> range(start: -5m)
  |> filter(fn:(r) => r._measurement == "energy_reading")
  |> last()
  |> pivot(rowKey:["_time"], columnKey:["_field"], valueColumn:"_value")
```
No point in 5 minutes ⇒ API answers `204` ⇒ UI shows the device offline.

*Range* — chart series, downsampled server-side:
```flux
  |> range(start: -{minutes}m)
  |> filter(_field == "current_A" or _field == "power_W")
  |> aggregateWindow(every: {every}, fn: mean, createEmpty: false)
  |> pivot(...)
```
`every` is regex-validated (`^\d{1,4}[smh]$`) — user input never lands raw in Flux.

*Daily* — energy and cost:
```flux
  |> range(start: -{days}d) |> filter(_field == "power_W")
  |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
```
then `kWh = mean_W × 24 h / 1000`, `cost = kWh × COST_PER_KWH`. The mean×24
approximation is exact when the cadence is uniform — which it is (firmware
publishes at a fixed 1 Hz); `integral()` is the documented switch if cadence ever
varies.

---

## 9. MQTT — the firmware boundary

### 9.1 The contract (source of truth: `firmware/include/config.h`, `firmware/src/network_task.cpp`)

| Direction | Topic | Payload | Cadence |
|---|---|---|---|
| board → software | `smile-iot/power` | `{"current_A":f,"power_W":f,"voltage_V":f,"outlet_state":"ON"\|"OFF","trip_latched":bool}` | 1 Hz |
| software → board | `smile-iot/command` | plain text `ON` · `OFF` · `RESET` (clears the overcurrent latch) | on demand, QoS 1 |

The backend treats this contract as read-only: field names, topic names, and
command strings appear once each in `config.py` and match the firmware constants.

### 9.2 Ingest worker (`backend/ingest/worker.py`)

- paho-mqtt v2 callbacks; subscribes with QoS 1; `reconnect_delay_set(1, 30)` for
  exponential backoff; survives the broker starting *after* the worker
  (`connect_async` + `loop_forever(retry_first_connection=True)`).
- Validation: payload must be a JSON object with numeric `current_A`, `power_W`,
  `voltage_V`. Failures are **counted and logged with a payload snippet** — the old
  stack dropped malformed messages silently.
- Writes through `WriteOptions(batch_size=50, flush_interval=5000, jitter_interval=500)`:
  the influxdb-client batches in its own thread, so a slow/down InfluxDB never
  blocks the MQTT loop (the old stack did synchronous writes inside the callback).
- Clean shutdown (SIGTERM/Ctrl-C): disconnect, `write_api.close()` (flushes the
  pending batch), close client — no readings lost on restart.
- Progress log every 60 readings: `N readings ingested (M rejected)`.

### 9.3 Command publisher (`backend/services/mqtt_publisher.py`)

Lazy module-level singleton behind a lock: first `POST /api/control/*` connects it
(`loop_start()` background thread), then it's reused. `publish()` uses QoS 1 +
`wait_for_publish(timeout=3)` so the API's `202` really means "accepted by the
broker" — and a dead broker surfaces as `503 broker_unavailable`, not a silent
success. `check_connection()` (used by `/api/system/status`) attempts the lazy
connect so the status chip reflects reachability.

Worker and publisher are **separate clients with separate lifecycles** — ingest
keeps archiving even if the API is down, and vice versa.

---

## 10. Frontend — Vite + React SPA

### 10.1 Dev topology

`vite.config.js` proxies `/api` → `http://127.0.0.1:5000`: the browser sees one
origin (:5173), so no CORS negotiation, no absolute URLs in code, and production
can serve the built `dist/` from anywhere that can reverse-proxy `/api`.

### 10.2 Auth flow

- `AuthContext` keeps `{token, user}` in `localStorage`; on mount it *validates*
  a stored token against `GET /auth/me` (catches expiry and deleted users).
- `api/client.js` is the single fetch wrapper: injects the Bearer header, parses
  the uniform error shape into a typed `ApiError`, and on **any** `401` wipes the
  session and flips the app to the login route via a registered handler.
- Route guards in `App.jsx`: unauthenticated → `/login`; `/admin` additionally
  requires `user.role === 'admin'` (the API enforces it again server-side).
- Login page handles the full reset flow; an emailed link lands on
  `/login?token=…` which pre-opens the confirm form.
- Trade-off, accepted and documented: tokens in `localStorage` are XSS-readable —
  fine for a LAN prototype, revisit before any exposure.

### 10.3 Live data model

`usePolling(fn, 5000)` — immediate call + interval, **skipping ticks while the tab
is hidden**. Each tick fires `latest` + `range` + `daily` + `status` in parallel
(`Promise.allSettled`, so one failing endpoint doesn't blank the page). The window
selector (15 min/60 min/3 h) maps to `range` params (`every` 10s/10s/1m).

| Page | Route | Consumes |
|---|---|---|
| Login | `/login` | `auth/login`, `password-reset/*` |
| Dashboard | `/` | `telemetry/*`, `control/*`, `system/status` |
| Profile | `/profile` | `auth/me`, `users/me/password` |
| Admin | `/admin` | `users*`, `admin/login-logs` |

### 10.4 Dashboard semantics

- **KPI tiles:** instant current/power from `latest`; avg + peak computed from the
  visible `range` window.
- **Status chips:** device online = `last_reading_age_s ≤ 10` (10 s ≈ 10 missed
  1 Hz beats); outlet ON/OFF from `latest`; broker from `mqtt_connected`.
- **Trip banner:** `trip_latched:true` renders a critical banner (icon + text, not
  color-alone) with a **Reset trip** button → `POST /control/reset-trip`. The old
  dashboard never surfaced this safety state.
- **Outlet buttons** disable the no-op direction (ON disabled while already ON) and
  explain confirmation-via-telemetry after publishing.
- **Charts** (Recharts): power area + current line + daily-energy bars. Colors come
  from the validated palette in `theme.js` (power = blue `#2a78d6`/`#3987e5`,
  current = aqua `#1baf7a`/`#199e70`, light/dark selected via `matchMedia` — hex is
  passed to the SVG marks because presentation attributes can't resolve CSS vars).
  Single-series charts ⇒ card titles name the series, no legends; 2 px strokes,
  hairline grid, 4 px rounded bar tops, themed tooltips. Page chrome uses CSS
  custom properties with a `prefers-color-scheme` dark block.

---

## 11. Ports & processes

| Thing | Where | Port | Started by |
|---|---|---|---|
| Mosquitto | Docker | 1883 | `docker compose up -d` |
| PostgreSQL | Docker | 5432 | 〃 |
| InfluxDB | Docker | 8086 | 〃 |
| Flask API | host | 5000 | `.venv/bin/python -m backend.app` |
| Ingest worker | host | — | `.venv/bin/python -m backend.ingest.worker` |
| Vite dev server | host | 5173 | `cd frontend && npm run dev` |

Setup-from-nothing and the no-hardware test recipe live in
[software_README.md](../software/software_README.md). Factory reset: stop the
processes, `docker compose down`, `rm -rf data/`, `docker compose up -d`, recreate
the scoped token, `init_db`.

---

## 12. Security model

| Control | Where |
|---|---|
| bcrypt password hashing (per-hash salt) | `services/postgres.py` |
| Failed-attempt lockout (5 → 15 min) + full login audit | 〃 |
| Neutral password-reset responses (no user enumeration) + 60 s cooldown + single-use 60-min tokens | `api/auth.py` |
| JWT expiry 30 min; role claim; `@admin_required`; self-delete blocked | API layer |
| Current password required to change your own | `api/users.py` |
| Scoped (single-bucket) InfluxDB token; zero secrets in source or git | `.env` + §3.3 |
| Local broker instead of public internet broker | compose |

**Accepted risks (prototype, LAN):** anonymous Mosquitto on the LAN; JWT in
`localStorage`; seeded `admin/admin123` until changed; Flask dev server (gunicorn
is the production path); no HTTPS.

---

## 13. Verification record (2026-07-08 → 09)

- **Auth:** bad login 401 · 5 failures → 423 with `locked_until` (correct password
  also refused while locked) · duplicate user 409 · wrong current password 403 ·
  self-delete 409 · reset request 202 (identical for unknown email), repeat 429.
- **Pipeline:** 20 contract-shaped fake readings + 1 malformed via `mosquitto_pub`
  → worker ingested 20, logged 1 rejection → `/latest`, `/range` (downsampled),
  `/daily` (kWh + €) all correct **with no browser open**.
- **Control:** `OFF`, `ON`, `RESET` posted through the API were received in order
  by a `mosquitto_sub` on `smile-iot/command`; invalid state → 400.
- **In-browser (Vite + preview):** login → live KPIs/charts from a 1 Hz publisher →
  outlet buttons → simulated 16.4 A overcurrent (`trip_latched:true`) raised the
  banner → **Reset trip** put `RESET` on the wire → post-reset telemetry cleared
  it. Admin page: create form, users table, audit log rendering.

---

## 14. Deferred work

| Item | Blocked on / note |
|---|---|
| Multi-device (Phase 5): devices/permissions UI over the ready tables | firmware must add `"mac"` to telemetry (or per-device topics) |
| Reflash boards to the LAN broker | compile-time `MQTT_BROKER` in `config.h`; bridge = `MQTT_HOST=broker.emqx.io` |
| Real SMTP for reset emails | fill SMTP vars in `.env` |
| pytest suite against the compose stack | — |
| Containerize API + worker (`restart: always`) | — |
| Mosquitto auth/ACLs, HTTPS, gunicorn | pre-exposure hardening |
