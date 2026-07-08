"""MQTT → InfluxDB ingest worker.

Runs 24/7, independent of the API and of any browser session — this is
the fix for the old Streamlit design where telemetry was only archived
while a dashboard tab was open.

Contract (firmware/src/network_task.cpp, 1 Hz):
  topic  smile-iot/power
  json   {"current_A":f, "power_W":f, "voltage_V":f,
          "outlet_state":"ON"|"OFF", "trip_latched":bool}

Design notes:
- Batched, async writes (influxdb-client WriteOptions) so a slow Influx
  never blocks the MQTT network loop — unlike the old sync-write-in-callback.
- Explicit nanosecond timestamps: server-assigned times could collide
  within one batch and silently overwrite points.
- outlet_state / trip_latched are FIELDS (not tags): one series per
  device, and last()+pivot on the read side yields a single row.
- Malformed payloads are logged, not silently dropped.

Run (from software/):  python -m backend.ingest.worker
"""

import json
import logging
import signal
import sys
import time

import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import WriteOptions
from paho.mqtt.client import CallbackAPIVersion

from backend import config

log = logging.getLogger("ingest")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

REQUIRED_NUMERIC = ("current_A", "power_W", "voltage_V")


def build_point(payload: dict) -> Point:
    point = (
        Point(config.INFLUX_MEASUREMENT)
        .tag("device", payload.get("mac", config.DEFAULT_DEVICE_TAG))
        .time(time.time_ns())
    )
    for field in REQUIRED_NUMERIC:
        point = point.field(field, float(payload[field]))
    point = point.field("outlet_state", str(payload.get("outlet_state", "UNKNOWN")))
    point = point.field("trip_latched", 1 if payload.get("trip_latched") else 0)
    return point


class IngestWorker:
    def __init__(self):
        self.influx = InfluxDBClient(
            url=config.INFLUX_URL, token=config.INFLUX_TOKEN, org=config.INFLUX_ORG
        )
        self.write_api = self.influx.write_api(
            write_options=WriteOptions(batch_size=50, flush_interval=5_000, jitter_interval=500)
        )
        self.client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id="smile-ingest-worker",
        )
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.received = 0
        self.rejected = 0

    # --- callbacks (paho network thread) ---
    def on_connect(self, client, userdata, connect_flags, reason_code, properties):
        if reason_code.is_failure:
            log.error("Broker refused connection: %s", reason_code)
            return
        client.subscribe(config.MQTT_TOPIC_TELEMETRY, qos=1)
        log.info("Connected to %s:%s, subscribed to %s",
                 config.MQTT_HOST, config.MQTT_PORT, config.MQTT_TOPIC_TELEMETRY)

    def on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        log.warning("Disconnected from broker (%s) — auto-reconnecting", reason_code)

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("payload is not a JSON object")
            self.write_api.write(bucket=config.INFLUX_BUCKET, record=build_point(payload))
            self.received += 1
            if self.received % 60 == 0:
                log.info("%d readings ingested (%d rejected)", self.received, self.rejected)
        except (ValueError, KeyError, TypeError) as exc:
            self.rejected += 1
            log.warning("Rejected payload on %s: %s (%r)", msg.topic, exc, msg.payload[:120])

    # --- lifecycle ---
    def run(self):
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        try:
            self.client.connect(config.MQTT_HOST, config.MQTT_PORT, keepalive=60)
        except Exception as exc:
            log.error("Cannot reach broker %s:%s (%s) — retrying via loop",
                      config.MQTT_HOST, config.MQTT_PORT, exc)
            self.client.connect_async(config.MQTT_HOST, config.MQTT_PORT, keepalive=60)
        try:
            self.client.loop_forever(retry_first_connection=True)
        except (KeyboardInterrupt, SystemExit):
            log.info("Shutting down: flushing writes…")
        finally:
            self.client.disconnect()
            self.write_api.close()   # flushes pending batch
            self.influx.close()
            log.info("Done. %d ingested, %d rejected.", self.received, self.rejected)


if __name__ == "__main__":
    IngestWorker().run()
