# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

SMILE-IoT is a non-invasive AC energy monitor: an ESP32 clamps a current sensor
around a mains cable, computes RMS current/power, and streams telemetry over
Wi-Fi/MQTT to a server that archives it and serves a web dashboard. It's a
solo/prototype project spanning three layers that live in separate top-level dirs:

- `firmware/` — ESP32 C++/FreeRTOS edge node (PlatformIO)
- `software/` — Python backend (Flask + ingest worker) and React dashboard
- `hardware/` — schematics, BOM, wiring docs (no build)

The single most important read for whole-system context is `PROJECT_GUIDE.md`
(self-contained, kept in sync with source, with file/line pointers). Per-layer
detail lives in `firmware/Firmware_README.md`, `software/software_README.md`, and
`docs/SOFTWARE_ARCHITECTURE_2026-07-09.md`.

## The MQTT contract (the seam between firmware and software)

Both sides must agree on this; it is the thing most likely to break silently.

- Telemetry: firmware **publishes** 1 Hz to `smile-iot/power`, JSON:
  `{"current_A":f,"power_W":f,"voltage_V":f,"outlet_state":"ON"|"OFF","trip_latched":bool}`
  (hand-rolled with `snprintf` in `firmware/src/network_task.cpp`).
- Commands: server **publishes** plain-text `ON` / `OFF` / `RESET` to
  `smile-iot/command` (QoS 1); firmware subscribes. The browser never touches MQTT.
- Firmware topic/broker constants: `firmware/include/config.h`. Server side:
  `software/backend/config.py` (`MQTT_TOPIC_*`). Changing a topic, field name, or
  unit requires editing **both** files.

When touching anything that crosses this boundary, prefer the `integration-architect`
agent to trace the end-to-end effect before editing either side.

## Data flow

`ESP32 → Mosquitto → ingest worker → InfluxDB` for time series; the Flask API reads
InfluxDB (energy readings) and PostgreSQL (users/auth/audit) and publishes relay
commands back to MQTT. The **ingest worker is a separate long-running process** from
the API — telemetry is archived 24/7 regardless of whether any dashboard is open.
Don't move ingestion into an API request path; that was the flaw in the old Streamlit
design this architecture replaced.

**Power is derived server-side.** The device has no voltage sensor, so grid voltage is
a configuration value, not a measurement. The ingest worker overrides the firmware's
`power_W`/`voltage_V`, computing `power_W = current_A × configured_voltage` from an
admin-editable setting in Postgres (`app_settings`, TTL-cached ~30 s in the worker;
changes are not retroactive). Only `current_A` is trusted from the payload. Admins edit
the value on the dashboard Admin page (`GET`/`PUT /api/settings/grid-voltage`); no
reflash needed.

## Firmware (`firmware/`)

PlatformIO, `board = esp32dev`, Arduino framework. `PubSubClient` (MQTT) is the
**only** external lib by design — JSON is hand-rolled and provisioning uses core
`WiFi.h`/`WebServer.h`/`DNSServer.h`/`Preferences.h`. Keep it that way; adding deps
is a deliberate decision.

```bash
cd firmware
pio run                                   # build
pio run -t upload && pio device monitor -b 115200   # flash + serial
pio run -t compiledb                      # regenerate compile_commands.json for clangd
```

Architecture: `main.cpp` only provisions Wi-Fi at boot, then spawns two
FreeRTOS tasks and lets `loop()` delete itself. The split is safety-motivated:

- `sensor_task.cpp` — samples the SCT-013, computes RMS, drives the relay, and runs
  the **overcurrent safety cutoff**. Pinned to core 1, higher priority, so network
  stalls can never delay a trip. The trip is *latched* (stays off until `RESET`/`OFF`).
- `network_task.cpp` — Wi-Fi/MQTT publish + command subscribe. Core 0, lower priority.
- The two tasks communicate only through `shared_state.cpp/.h` (readings out, relay
  commands in). Don't add cross-task state outside that module.

Sensor math gotcha (documented in `sensor_task.cpp`): convert ADC counts → volts
*before* applying `CT_CALIBRATION`; applying calibration to raw counts was the
original bug. Voltage is a fixed nominal in firmware (`GRID_VOLTAGE_V` 230 V) — no
voltage-sensing hardware — so the firmware's `power_W`/`voltage_V` are advisory; the
server recomputes power from the admin-configured voltage (see Data flow above).

## Software (`software/`)

Infra (broker + DBs) runs in Docker; the Flask API, ingest worker, and React dev
server run on the host. `software/backend/config.py` is the **only** module that
reads `.env`/`os.environ` — everything else imports settings from it.

First-time setup and the three run commands are in `software/software_README.md`.
The essentials:

```bash
cd software
cp .env.example .env                      # then fill secrets (commands are in the file)
docker compose up -d                      # mosquitto :1883, postgres :5432, influxdb :8086
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
.venv/bin/python -m backend.scripts.init_db     # tables + seed admin/admin123

# run (three terminals, from software/):
.venv/bin/python -m backend.ingest.worker # telemetry archiver
.venv/bin/python -m backend.app           # Flask API on :5000
cd frontend && npm install && npm run dev # dashboard on :5173
```

Backend layout: `backend/api/` are Flask blueprints — `system` (mounted at `/api`,
gives `/api/health` and `/api/system/status`), plus `auth`, `users`, `telemetry`,
`control`, `settings` under `/api/<name>` — all registered in `backend/app.py`.
`backend/services/` holds the integrations — `postgres.py` (auth/lockout/audit/
`app_settings`), `influx.py` (reads), `mqtt_publisher.py` (relay commands),
`emailer.py`. Auth is JWT (`flask-jwt-extended`); `backend/api/helpers.py` supplies
both the uniform `{error, message}` payload (`err`) and the `@admin_required`
gate that every admin-only route uses. App-wide error handlers live in `app.py`.

Frontend is Vite + React (`react-router-dom`, `recharts`). The dev server proxies
`/api` → `:5000`, so client code uses relative URLs and there's effectively no CORS
concern in dev.

### Verifying changes (there is no test suite)

Nothing in this repo has automated tests or a linter — no pytest/ESLint/`pio test`
config exists, and `frontend/package.json` has only `dev`/`build`/`preview`. Don't
go looking for a test command; verify by building and exercising the running stack:

- firmware — `cd firmware && pio run` (compile is the check)
- backend — start the API and hit it, e.g. `curl localhost:5000/api/health`
- frontend — `npm run build` catches import/syntax breakage

Fake the firmware over MQTT rather than needing a board:

```bash
docker exec smile_mosquitto mosquitto_pub -t smile-iot/power \
  -m '{"current_A":2.4,"power_W":552.0,"voltage_V":230.0,"outlet_state":"ON","trip_latched":false}'
docker exec smile_mosquitto mosquitto_sub -t smile-iot/command -v   # watch dashboard commands
```

`firmware/tools/mqtt_debug.py` does both interactively. It has its **own** venv
(`cd firmware/tools && python3 -m venv .venv && ./.venv/bin/pip install -r
requirements.txt`) — separate from `software/.venv` — and defaults to local
Mosquitto; `--host/--username/--password` to reach a board still on `broker.emqx.io`.

## Hardware (`hardware/`)

Docs only — nothing builds here. `hardware_README.md` is the wiring/BOM reference;
`PCB_DESIGN_v1.md` is the v1 board design, with `kicad/smile-iot-v1.net` (a netlist
written as a wiring spec, using *function* pin names) and
`kicad/SYMBOL_FOOTPRINT_ASSIGNMENTS.md` mapping those to KiCad 8 symbols/footprints.
The netlist is a spec to draw from in eeschema, not an authoritative KiCad export —
function pin names won't auto-match numeric pads on the ESP32 module, relay, HLK-PM01
or jack. Mains-side changes go through `hardware-advisor` first.

## Known drift to watch for

- **Broker address is a hardcoded DHCP IP:** `firmware/include/config.h` sets
  `MQTT_BROKER` to `192.168.1.254` (the dev machine's LAN address). If that DHCP
  lease changes, boards silently stop reaching the broker and need a reflash —
  give the server a DHCP reservation. Boards flashed before 2026-08-04 still point
  at the public `broker.emqx.io` and must be reflashed to reach the local stack.
- **Secrets are per-machine:** `.env` and `.venv/` are gitignored. If `.env` is
  missing/empty, re-run the setup copy step — nothing reads secrets from elsewhere.

## Working conventions

- This is a one-person project — favor clean rebuilds over patching legacy drift,
  functional-first simplicity, and keeping docs updated alongside code changes.
- Per-directory `*_README.md` files are maintained as real documentation; update the
  relevant one when you change how a layer works, and keep `PROJECT_GUIDE.md` honest
  (it claims every statement is checked against source).
- Specialized subagents exist for each layer (`firmware-engineer`, `backend-engineer`,
  `hardware-advisor`, `integration-architect`, `docs-writer`) — prefer them over the
  generalist for layer-specific work, and consult `hardware-advisor` before any change
  touching how the device interfaces with mains AC.
