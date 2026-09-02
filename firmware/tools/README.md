# firmware/tools

Host-side scripts for exercising the firmware over MQTT without a phone or the web dashboard.

## mqtt_debug.py

Connects to a broker/topics, prints incoming telemetry from `smile-iot/power`, and lets you
publish `ON` / `OFF` / `RESET` to `smile-iot/command` interactively — for exercising the
backend (ingest worker + API) without a phone or a physical board.

Defaults to the **local Mosquitto** from `software/docker-compose.yml`
(`localhost:1883`, anonymous — no credentials), matching how `backend/config.py` and the
ingest worker connect. This is *not* the same broker as `firmware/include/config.h`'s
`MQTT_BROKER`, which (for boards not yet reflashed) still points at the public
`broker.emqx.io` with the credentials hardcoded there. Point this tool at whichever broker
the thing you're testing against is actually on — mismatching them silently gives you zero
traffic in either direction, since neither side errors, they just never meet.

### Setup (first time)

```bash
cd firmware/tools
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

### Run

```bash
./.venv/bin/python mqtt_debug.py                    # local Mosquitto (default) — talks to the backend
```

Bridge to the public broker instead, e.g. to talk to a board that hasn't been reflashed yet:

```bash
./.venv/bin/python mqtt_debug.py --host broker.emqx.io --username 1211189 --password isep
```

At the `>` prompt: `on`, `off`, `reset`, or `quit`.

Verified against the local Mosquitto stack on 2026-07-21: connect (anonymous), subscribe to
`smile-iot/power`, and publish to `smile-iot/command` all confirmed working with the ingest
worker and API running locally. (Public-broker mode was verified separately on 2026-07-08,
before the local Mosquitto migration.)
