# Software

Python application layer for telemetry ingestion and data visualization.

## Architecture
This directory contains two decoupled services communicating via a local data store:
1. **`listener.py`:** Background MQTT client. Subscribes to the broker and writes incoming telemetry payloads to local storage (`data.json`).
2. **`dashboard.py`:** Streamlit web interface. Polls the local storage and renders real-time time-series charts and KPIs.

## Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Execution

Run both services concurrently in separate terminal sessions

Terminal 1 - Start the ingestion deamon
```bash
python listener.py
```

Terminal 2 - Boot the web UI 
```bash
streamlit run dashboard.py
```


