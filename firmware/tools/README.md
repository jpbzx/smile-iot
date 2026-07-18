# firmware/tools

Host-side scripts for exercising the firmware over MQTT without a phone or the Streamlit dashboard.

## mqtt_debug.py

Connects to the same broker/topics/credentials the firmware uses (`config.h`), prints incoming
telemetry from `smile-iot/power`, and lets you publish `ON` / `OFF` / `RESET` to `smile-iot/command`
interactively.

### Setup (first time)

```bash
cd firmware/tools
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

### Run

```bash
./.venv/bin/python mqtt_debug.py
```

Override broker/topics/credentials if needed:

```bash
./.venv/bin/python mqtt_debug.py --host broker.emqx.io --username 1211189 --password isep
```

At the `>` prompt: `on`, `off`, `reset`, or `quit`.

Verified against the live public broker (`broker.emqx.io`) on 2026-07-08: connect, subscribe, and
publish all confirmed working independent of any real device being online.
