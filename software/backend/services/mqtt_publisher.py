"""Outbound MQTT — the API's single publisher connection for relay commands.

The firmware (network_task.cpp) accepts plain-text ON / OFF / RESET on
the command topic; QoS 1 matches what the old dashboard used.
"""

import logging
import threading
import time

import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion

from backend import config

log = logging.getLogger(__name__)

_lock = threading.Lock()
_client: mqtt.Client | None = None

VALID_COMMANDS = ("ON", "OFF", "RESET")


def _ensure_client() -> mqtt.Client | None:
    global _client
    with _lock:
        if _client is not None and _client.is_connected():
            return _client
        try:
            client = mqtt.Client(
                callback_api_version=CallbackAPIVersion.VERSION2,
                client_id="smile-api-publisher",
            )
            client.connect(config.MQTT_HOST, config.MQTT_PORT, keepalive=30)
            client.loop_start()
            _client = client
            log.info("MQTT publisher connected to %s:%s", config.MQTT_HOST, config.MQTT_PORT)
            return _client
        except Exception as exc:
            log.warning("MQTT publisher connect failed: %s", exc)
            _client = None
            return None


def is_connected() -> bool:
    return _client is not None and _client.is_connected()


def check_connection() -> bool:
    """Truthful broker reachability for /api/system/status: connects the
    lazy client if needed instead of reporting 'false' before the first
    command was ever published."""
    if is_connected():
        return True
    client = _ensure_client()
    if client is None:
        return False
    # loop_start() acks the connect asynchronously; give it a moment
    for _ in range(10):
        if client.is_connected():
            return True
        time.sleep(0.05)
    return client.is_connected()


def publish_command(command: str) -> bool:
    """Publish ON/OFF/RESET to the command topic. Returns delivery success."""
    if command not in VALID_COMMANDS:
        raise ValueError(f"invalid command {command!r}")
    client = _ensure_client()
    if client is None:
        return False
    try:
        info = client.publish(config.MQTT_TOPIC_COMMAND, command, qos=1)
        info.wait_for_publish(timeout=3)
        return info.is_published()
    except Exception as exc:
        log.warning("MQTT publish failed: %s", exc)
        return False
