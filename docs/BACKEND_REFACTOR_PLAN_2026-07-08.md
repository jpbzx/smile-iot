# SMILE-IoT — Backend Refactor Plan: Flask + React

**Date:** 2026-07-08
**Status:** DELIVERED 2026-07-09 on branch `feature/flask-react-backend` —
executed as a full teardown + from-scratch rebuild rather than a phased
migration (user decision): old Streamlit stack, containers, images and data
wiped; Phases 0–4 built and verified in one pass. Phase 5 (multi-device)
remains deferred. Deviations from this plan: English DB schema (no legacy
data survived, so no migration constraint), `GET /api/admin/login-logs`
delivered early, immediate cutover (no `legacy_streamlit/` transition).
**As-built reference:**
[SOFTWARE_ARCHITECTURE_2026-07-09.md](SOFTWARE_ARCHITECTURE_2026-07-09.md).
**Decisions (2026-07-08):** local **Mosquitto** confirmed (risk #1/#2 accepted:
firmware keeps pointing at `broker.emqx.io` until reflashed — bridge via `.env`);
**single-board scope** confirmed — Phase 5 (devices/multi-board) deferred.
**Companion doc:** [SOFTWARE_ARCHITECTURE_2026-07-08.md](SOFTWARE_ARCHITECTURE_2026-07-08.md)
— the current-state overview this plan replaces piece by piece.

---

## 1. Goals & non-goals

**Goals**
1. **Functional first.** Every phase ends with something runnable and verifiable
   end-to-end (curl or browser + `firmware/tools/mqtt_debug.py`). No phase depends on a
   later one to be demonstrable.
2. **Feature parity** with the Streamlit app (auth + lockout + audit, password reset,
   profile, admin user creation, live dashboard, outlet control) — *then* finish what
   Streamlit left as TODOs (real history from InfluxDB, trip-latch visibility + RESET,
   device management).
3. **Fix the architectural flaws** rather than patch them:
   - ingestion decoupled from UI sessions (dedicated worker → no data loss),
   - browser no longer talks MQTT concepts; it talks HTTP to *our* API,
   - all config from `.env`, zero secrets in source.
4. **Simpler than it looks:** two small Python processes + one static SPA. No ORM, no
   WebSockets, no Redis, no task queue.

**Non-goals (for now)**
- Multi-device support in the UI (schema is ready; firmware sends no device id yet).
- HTTPS / internet deployment (LAN prototype).
- Refresh tokens / "remember me" (re-login after 30 min is acceptable).

---

## 2. Why Flask + React (pain → fix)

| Streamlit pain (see companion doc §8) | Flask + React fix |
|---|---|
| MQTT client lives inside a UI session → data only ingested while a tab is open | Standalone **ingest worker** process, runs 24/7 |
| Sync Influx write inside paho callback stalls the network loop | Worker uses influxdb-client **batching** API |
| Full-script rerun + `time.sleep()` refresh loop holds a server thread per user | SPA polls a cheap JSON endpoint; server is stateless |
| UI, business logic, and ingestion in one process | Three cleanly separated concerns: worker / API / SPA |
| Browser configures the broker and publishes MQTT directly | Broker is server-side config; browser calls `POST /api/control/*` |
| History panel fake (no Influx read path) | First-class `/api/telemetry/*` read endpoints |

---

## 3. Target architecture

```text
┌─────────┐ smile-iot/power  ┌───────────┐ subscribe ┌───────────────┐  batched  ┌──────────┐
│  ESP32  ├─────────────────►│ Mosquitto ├──────────►│ ingest worker ├──────────►│ InfluxDB │
│ firmware│◄─────────────────┤ (compose) │           │ (python proc) │  writes   │ (compose)│
└─────────┘ smile-iot/command└─────▲─────┘           └───────────────┘           └────▲─────┘
              ON/OFF/RESET         │ publish                                          │ Flux
                                   │                                                  │ queries
                            ┌──────┴──────────────────────────────────────────────────┴──┐
                            │                    Flask API  (:5000)                       │
                            │  /api/auth  /api/users  /api/telemetry  /api/control  ...   │
                            └──────▲───────────────────────────────┬──────────────────────┘
                                   │ JSON + JWT                    │ psycopg2
                            ┌──────┴──────┐                 ┌──────▼──────┐
                            │  React SPA  │                 │ PostgreSQL  │
                            │ (Vite build)│                 │  (compose)  │
                            └─────────────┘                 └─────────────┘
```

**Key property:** the ingest worker and the API share **no memory** — InfluxDB is the
interface. "Latest reading" = last point in the bucket. Either process can restart
independently; readings keep flowing as long as the worker is up.

---

## 4. Stack & decisions (with rationale)

| Decision | Choice | Why |
|---|---|---|
| Web framework | Flask, app-factory + blueprints | Team knows Python; minimal ceremony |
| Auth | `flask-jwt-extended`, 30-min access token, `role` claim, `@admin_required` decorator | Stateless API; mirrors current `SESSION_TIMEOUT_MIN`; no CORS-cookie headaches with Vite dev server |
| DB access | Raw `psycopg2` (port `postgres_manager.py` almost verbatim) | That code is already correct (bcrypt, lockout, audit, tokens) — porting beats rewriting; no ORM to learn |
| Time series | `influxdb-client`; worker writes with `WriteOptions(batch_size=50, flush_interval=5_000)` | Non-blocking, batched — fixes callback-stall issue |
| MQTT | `paho-mqtt` v2 API. Worker = subscriber; API holds one publisher client for commands | One broker connection per concern |
| Realtime UI | **Polling** `GET /api/telemetry/latest` every 5 s | Simplest thing that works at 1 Hz telemetry; SSE/WebSocket is a later optimization, not a requirement |
| Frontend | React 18 + Vite, `react-router`, fetch wrapper, Context for auth, **Recharts** for charts | Standard, boring, documented everywhere |
| Broker | **Mosquitto in docker-compose** (allow LAN), keep `broker.emqx.io` as fallback env value | Removes "anyone on the internet can switch our relay"; env-switchable for demos |
| Serving | Dev: Vite :5173 + Flask :5000 with CORS. "Prod": `npm run build`, Flask serves `frontend/dist` | Zero extra infra |
| Testing | `pytest` against the compose databases; `mqtt_debug.py` for E2E | Functional-first: test the real stack |

---

## 5. Proposed layout

```text
software/
├── backend/
│   ├── app.py                 # create_app() factory + entrypoint
│   ├── config.py              # THE single place that reads .env
│   ├── requirements.txt       # pinned
│   ├── api/                   # one blueprint per resource
│   │   ├── auth.py            #   /api/auth/*
│   │   ├── users.py           #   /api/users*
│   │   ├── telemetry.py       #   /api/telemetry/*
│   │   ├── control.py         #   /api/control/*
│   │   ├── system.py          #   /api/health, /api/system/status
│   │   └── devices.py         #   /api/devices*          (Phase 5)
│   ├── services/
│   │   ├── postgres.py        # ported postgres_manager (unchanged logic)
│   │   ├── influx.py          # read queries (latest / range / daily) + health ping
│   │   ├── mqtt_publisher.py  # lazy singleton paho client for commands
│   │   └── emailer.py         # ported as-is
│   ├── ingest/
│   │   └── worker.py          # python -m backend.ingest.worker
│   ├── scripts/
│   │   └── init_db.py         # schema + seed admin (ported init_db)
│   └── tests/
├── frontend/
│   ├── package.json / vite.config.js
│   └── src/
│       ├── api/client.js      # fetch wrapper: base URL, JWT header, 401 → /login
│       ├── auth/AuthContext.jsx
│       ├── pages/  Login.jsx  Dashboard.jsx  Admin.jsx  Profile.jsx
│       ├── components/ KpiCards  PowerChart  CurrentChart  OutletControl
│       │              TripBanner  UserTable  DailyHistory
│       └── hooks/usePolling.js
├── docker-compose.yml         # + mosquitto:2 service (later: api & ingest containers)
├── mosquitto/mosquitto.conf
├── .env                       # single source of config for compose + backend
└── legacy_streamlit/          # old app moves here at cutover (Phase 3), deleted Phase 5
```

---

## 6. Data model (deliberately unchanged)

**PostgreSQL** — identical tables (`utilizadores`, `dispositivos`, `acessos_dispositivos`,
`login_logs`, `password_reset_tokens`); `init_db.py` is a port of the existing one, so
current databases keep working. (Optional EN table renames are a Phase-5 cleanup, not
worth a migration now.)

**InfluxDB** — same bucket/measurement so history stays queryable:
measurement `energy_reading`, tags `device`, `outlet_state`; fields `current_A`,
`power_W`, `voltage_V` **+ new field `trip_latched` (0/1)** — currently dropped by the
Streamlit ingester.

---

## 7. API endpoint map (complete)

Conventions: JSON everywhere; errors are `{"error": "<code>", "message": "<human>"}`;
`Authorization: Bearer <jwt>` unless marked *public*; timestamps ISO-8601 UTC.

### 7.1 Auth — `backend/api/auth.py`

| Method & path | Auth | Request body | Success | Errors |
|---|---|---|---|---|
| `POST /api/auth/login` | public | `{"username","password"}` | `200 {"access_token", "user":{"id","username","role"}}` | `401 invalid_credentials` (same for unknown user — no enumeration), `423 account_locked {"locked_until"}` |
| `GET /api/auth/me` | bearer | — | `200 {"id","username","email","role"}` | `401` |
| `POST /api/auth/password-reset/request` | public | `{"email"}` | `202 {"message":"If the email exists, a reset link was sent."}` — **always**, even on unknown email or SMTP failure (logged server-side) | `429 too_many_requests` (per-email cooldown 60 s) |
| `POST /api/auth/password-reset/confirm` | public | `{"token","new_password"}` | `200 {"message":"password_updated"}` | `400 invalid_token \| token_used \| token_expired \| weak_password` |

Login side effects (ported logic): bump `failed_attempts`, lock after
`MAX_FAILED_ATTEMPTS` for `LOCKOUT_MINUTES`, append to `login_logs`. JWT carries
`sub=user_id`, claims `{role, username}`, TTL `SESSION_TIMEOUT_MIN` (30 min). Logout is
client-side token discard.

### 7.2 Users — `backend/api/users.py`

| Method & path | Auth | Request body | Success | Errors |
|---|---|---|---|---|
| `GET /api/users` | admin | — | `200 [{"id","username","email","role","locked_until"}]` | `401/403` |
| `POST /api/users` | admin | `{"username","email","password","role"}` | `201 {"id"}` | `400 validation` (username ≥3, password ≥5, email has `@` — same rules as today), `409 duplicate` |
| `PATCH /api/users/{id}` | admin | `{"role"}` | `200` | `404`, `400` |
| `DELETE /api/users/{id}` | admin | — | `204` | `404`, `409 cannot_delete_self` |
| `PUT /api/users/me/password` | bearer | `{"current_password","new_password"}` | `200` | `403 wrong_current_password`, `400 weak_password` |

> Improvement over Streamlit: changing your own password now **requires the current
> password** (companion doc §8, issue 11).

### 7.3 Telemetry — `backend/api/telemetry.py` (reads InfluxDB only)

| Method & path | Auth | Query params | Success | Errors |
|---|---|---|---|---|
| `GET /api/telemetry/latest` | bearer | — | `200 {"timestamp","current_A","power_W","voltage_V","outlet_state","trip_latched"}` | `204` if no point in last 5 min |
| `GET /api/telemetry/range` | bearer | `minutes` (default 60, max 1440), `every` (downsample window, default `10s`) | `200 {"points":[{"t","current_A","power_W"},…]}` | `400 bad_params` |
| `GET /api/telemetry/daily` | bearer | `days` (default 30, max 365) | `200 {"days":[{"date","energy_kWh","cost_eur"}]}` | — |

Flux sketches (implemented in `services/influx.py`):

```python
# latest:  range(start:-5m) |> last()
# range:   range(start:-{m}m) |> aggregateWindow(every:{every}, fn:mean)
# daily:   range(start:-{d}d) |> filter(_field=="power_W")
#          |> aggregateWindow(every:1d, fn:mean)
#          |> map(kWh = meanW * 24 / 1000)      # valid at fixed 1 Hz cadence;
#                                               # switch to integral() if cadence varies
# cost_eur = kWh * COST_PER_KWH (0.25, from config)
```

### 7.4 Control — `backend/api/control.py` (publishes MQTT, mirrors firmware contract)

| Method & path | Auth | Request body | Success | Errors |
|---|---|---|---|---|
| `POST /api/control/outlet` | bearer | `{"state":"ON"\|"OFF"}` | `202 {"published":true}` | `400 invalid_state`, `503 broker_unavailable` |
| `POST /api/control/reset-trip` | bearer | `{}` | `202 {"published":true}` | `503 broker_unavailable` |

Publishes plain-text `ON`/`OFF`/`RESET` to `MQTT_TOPIC_COMMAND` (`smile-iot/command`),
QoS 1 — exactly what `network_task.cpp:mqttCallback()` parses. `202` (not `200`) because
delivery to the ESP32 is asynchronous; the UI confirms by watching `outlet_state` /
`trip_latched` flip in `/latest`.

### 7.5 System — `backend/api/system.py`

| Method & path | Auth | Success | Notes |
|---|---|---|---|
| `GET /api/health` | public | `200 {"status":"ok"}` | liveness for compose/monitoring |
| `GET /api/system/status` | bearer | `200 {"mqtt_connected","last_reading_age_s","postgres_ok","influx_ok"}` | `last_reading_age_s` from Influx last-point timestamp → the dashboard's "device online/offline" signal |

### 7.6 Audit — Phase 4

| Method & path | Auth | Query | Success |
|---|---|---|---|
| `GET /api/admin/login-logs` | admin | `limit` (default 100) | `200 [{"username","success","reason","timestamp"}]` |

### 7.7 Devices — Phase 5 (finishes the Streamlit TODOs; tables already exist)

| Method & path | Auth | Request body | Success | Errors |
|---|---|---|---|---|
| `GET /api/devices` | bearer | — | `200` list — admin sees all; user sees only assigned (`acessos_dispositivos`) | — |
| `POST /api/devices` | admin | `{"mac_address","name","current_limit"}` | `201 {"id"}` | `409 duplicate_mac`, `400` |
| `PATCH /api/devices/{id}` | admin | any of `{"name","current_limit"}` | `200` | `404` |
| `DELETE /api/devices/{id}` | admin | — | `204` | `404` |
| `PUT /api/devices/{id}/users` | admin | `{"user_ids":[…]}` (replaces assignment set) | `200` | `404`, `400 unknown_user` |

> Blocked on a firmware coordination point: telemetry carries no device id today. Phase
> 5 needs the firmware to add `"mac"` to the payload (or per-device topics
> `smile-iot/<mac>/power`) before per-device filtering means anything.

---

## 8. Frontend map

| Route | Page | Guard | Endpoints consumed |
|---|---|---|---|
| `/login` | Login + "forgot password" (request + confirm forms) | public | `auth/login`, `password-reset/request`, `password-reset/confirm` |
| `/` | Dashboard: KPI cards (current, power, avg/peak over window), power & current charts, outlet ON/OFF, **trip banner + RESET button**, device-online badge, daily kWh/€ history | JWT | `telemetry/latest` (poll 5 s), `telemetry/range`, `telemetry/daily`, `control/*`, `system/status` |
| `/profile` | Username/role, change password | JWT | `auth/me`, `users/me/password` |
| `/admin` | User table + create/delete/role, login-log viewer, device manager (P5) | JWT + `role==admin` | `users*`, `admin/login-logs`, `devices*` |

Cross-cutting: `AuthContext` stores the JWT (localStorage — acceptable XSS trade-off for
a LAN prototype, noted in §11); `api/client.js` injects the header and redirects to
`/login` on any `401`; `usePolling(fn, 5000)` drives the live data.

---

## 9. Configuration (single `.env`, read only by `backend/config.py` + compose)

```ini
# Postgres
POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB     # container init
DB_HOST=localhost  DB_PORT=5432 ...                 # backend (localhost, NOT service name)
# InfluxDB  (token READ FROM ENV — rotated; never in source again)
INFLUX_URL=http://localhost:8086
INFLUX_TOKEN= / INFLUX_ORG=smile_org / INFLUX_BUCKET=energy_data
# MQTT
MQTT_HOST=localhost  MQTT_PORT=1883                 # mosquitto; set broker.emqx.io to demo without LAN broker
MQTT_TOPIC_TELEMETRY=smile-iot/power
MQTT_TOPIC_COMMAND=smile-iot/command
# Auth
JWT_SECRET_KEY=                                     # new — generate once
SESSION_TIMEOUT_MIN=30  MAX_FAILED_ATTEMPTS=5  LOCKOUT_MINUTES=15
# SMTP (unchanged)  +  COST_PER_KWH=0.25
```

---

## 10. Phased delivery plan (functional-first: every phase ships something you can run)

### Phase 0 — Infra hygiene (½ day) *(valuable even if the refactor stalls)*
- **Rotate the InfluxDB admin token**; remove it from `db/influx_manager.py`; env-read it.
- Fix `.env` (`DB_HOST=localhost`), add the new vars from §9.
- Add `mosquitto` service to docker-compose (+ minimal `mosquitto.conf`, port 1883).
- `backend/scripts/init_db.py` (ported `init_db`).
- ✅ **Accept:** `docker compose up -d` → `init_db.py` → psql shows 5 tables;
  `mqtt_debug.py` traffic visible via `mosquitto_sub -t 'smile-iot/#'`.

### Phase 1 — Flask skeleton + auth (1–2 days)
- App factory, `config.py`, CORS, error-format handler, `/api/health`.
- Port `postgres_manager` → `services/postgres.py`; auth + users blueprints (§7.1–7.2).
- ✅ **Accept (curl):** login → JWT; 5 bad passwords → `423` + `login_logs` rows;
  `/me` 200 with token, 401 without; `users/me/password` rejects wrong current password.

### Phase 2 — Ingest worker + telemetry reads (1–2 days) *(the architectural win)*
- `ingest/worker.py`: subscribe, validate JSON, batched Influx writes incl.
  `trip_latched`; log malformed payloads (don't drop silently); auto-reconnect.
- `services/influx.py` + telemetry blueprint (§7.3); system status (§7.5).
- ✅ **Accept:** with **no browser anywhere**, `mqtt_debug.py` (or real ESP32) publishing
  → Influx point count grows; `/latest` returns fresh data; `/range?minutes=10` returns
  downsampled series; `/daily` returns kWh ≠ 0 after some traffic.

### Phase 3 — React MVP → **cutover** (2–3 days)
- Vite scaffold, AuthContext, login page, dashboard (KPIs, 2 charts, outlet control,
  trip banner + RESET, online badge), polling.
- ✅ **Accept (E2E):** login in browser → live values move; TURN OFF → `outlet_state`
  flips within ~2 s; simulated overcurrent (`mqtt_debug.py` publishing
  `trip_latched:true`) shows banner; RESET clears it.
- **Cutover:** move Streamlit app to `software/legacy_streamlit/`; update READMEs.

### Phase 4 — Parity completion (1–2 days)
- Profile page; forgot-password UI; admin: user table, create/delete/role, login-log
  viewer (§7.6). Email flow verified against real SMTP.
- ✅ **Accept:** feature-parity matrix (§12) all ✔ except devices.

### Phase 5 — Devices, hardening, cleanup (2–3 days, needs firmware coordination)
- Devices blueprint + admin UI (§7.7); firmware adds `mac` to payload (or per-device
  topics); worker tags points with the real MAC.
- Pin dependencies; `pytest` suite (auth, telemetry, control against compose stack);
  optional: mosquitto auth, rate-limit login, containerize `api` + `ingest`.
- Delete `legacy_streamlit/`, dead files (`utils/database.py`), stale docs.

**Total: ~8–12 working days** at student-project pace, demoable after every phase.

### Dev workflow (daily loop from Phase 2 on)

```bash
docker compose up -d                       # postgres + influx + mosquitto
python -m backend.ingest.worker            # terminal 1
flask --app backend.app run --debug        # terminal 2  (:5000)
cd frontend && npm run dev                 # terminal 3  (:5173, proxies /api)
python firmware/tools/mqtt_debug.py        # optional: fake ESP32
```

---

## 11. Risks & open decisions

| # | Risk / decision | Position |
|---|---|---|
| 1 | **Firmware broker host is a compile-time constant** (`config.h`) — pointing firmware at LAN mosquitto needs a reflash | Accept for now; later add a broker field to the provisioning portal. Until reflashed, set `MQTT_HOST=broker.emqx.io` in `.env` and everything still works |
| 2 | Public broker = anyone can command the relay | Solved at Phase 0 by mosquitto for LAN use; demo-day fallback documented |
| 3 | JWT in localStorage is XSS-readable | Accepted for LAN prototype; noted for any future hardening pass |
| 4 | No device id in telemetry | Single-device assumption until Phase 5 firmware change |
| 5 | Old Influx token lives in git history | Rotation (Phase 0) makes the leaked value worthless — no history rewrite needed |
| 6 | Two processes to keep running (api + worker) | `restart: always` once containerized in Phase 5; till then two terminals |

---

## 12. Feature parity matrix

| Feature (Streamlit today) | New home | Phase |
|---|---|---|
| Login, bcrypt, lockout, audit log | `POST /api/auth/login` + ported service | 1 |
| 30-min inactivity timeout | JWT TTL 30 min | 1 |
| Password reset (request + token confirm, neutral messages, cooldown) | `password-reset/*` | 1 (API) / 4 (UI) |
| Change own password | `PUT /api/users/me/password` (**+ requires current pw**) | 1 (API) / 4 (UI) |
| Admin: create user | `POST /api/users` | 1 (API) / 4 (UI) |
| Live KPIs + power/current charts | `/telemetry/latest` + `/range`, Recharts | 2–3 |
| Outlet ON/OFF | `POST /api/control/outlet` | 2–3 |
| Trip latch visibility + RESET *(missing today)* | `/latest.trip_latched` + `POST /api/control/reset-trip` | 2–3 |
| Daily kWh/€ history *(fake today)* | `GET /api/telemetry/daily` | 2–3 |
| 24/7 ingestion → InfluxDB *(session-bound today)* | ingest worker | 2 |
| Device online indicator *(implicit today)* | `system/status.last_reading_age_s` | 2–3 |
| Broker host/topic UI in sidebar | **Dropped deliberately** — server-side `.env` config; browser should not own the broker connection | — |
| Admin: device mgmt + user↔device assignment *(TODO stubs today)* | `devices*` endpoints + UI | 5 |
