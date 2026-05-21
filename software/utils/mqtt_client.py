"""
SMILE-IoT — MQTT subscriber client.

Handles paho-mqtt callbacks, connection lifecycle, and the thread-safe
queue that bridges the paho background thread with Streamlit's main thread.

No Streamlit widget calls are made inside callbacks (they would crash).
The sync_mqtt() function is the single transfer point: call it at the top of
every Streamlit rerun to drain queued messages into session_state.

Data Format (from ESP32):
  "5.23,5.18,1,5.20" → (current_fast, precise, state, avg)
"""

import queue

import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion
import streamlit as st

from utils.simulated_data import MAX_BUFFER_SIZE

from db.influx_manager import influx_db

# ---------------------------------------------------------------------------
# Module-level MQTT primitives (shared across threads via Python GIL)
#
# Why module-level and NOT session_state?
#   paho callbacks fire in a C-extension background thread where
#   st.session_state is invalid.  A plain queue.Queue and dict are safe
#   for cross-thread reads/writes under the GIL for a single-user prototype.
# ---------------------------------------------------------------------------
_mqtt_queue: queue.Queue = queue.Queue()
_mqtt_conn_state: dict = {"connected": False, "error": ""}


# ---------------------------------------------------------------------------
# paho callbacks  (background thread — NO st.* calls)
# ---------------------------------------------------------------------------

def _parse_energy_reading(payload_str: str) -> dict | None:
    """
    Parse compact energy reading format: "current_fast,precise,state,avg"
    Example: "5.23,5.18,1,5.20" → {current_A, precise_A, state, avg}
    
    Returns dict or None if parsing fails.
    """
    try:
        parts = payload_str.strip().split(',')
        if len(parts) != 4:
            return None
        
        return {
            "current_A": float(parts[0]),      # Fast reading (100 samples)
            "precise_A": float(parts[1]),      # Precise reading (2500 samples)
            "state": bool(int(parts[2])),      # 1=ON, 0=OFF
            "avg": float(parts[3]),            # Average over 5s
            # Legacy fields for backward compatibility with InfluxDB
            "outlet_state": "ON" if int(parts[2]) else "OFF",
            "power_W": 230.0 * float(parts[1]),  # Estimate: V * I
            "voltage_V": 230.0
        }
    except (ValueError, IndexError, AttributeError):
        return None


def _on_connect(
    client: mqtt.Client,
    userdata: dict,
    connect_flags,
    reason_code,
    properties,
) -> None:
    if reason_code == 0:
        _mqtt_conn_state["connected"] = True
        _mqtt_conn_state["error"] = ""
        client.subscribe(userdata["topic"])
    else:
        _mqtt_conn_state["connected"] = False
        _mqtt_conn_state["error"] = f"Broker refused connection (code {reason_code})"


def _on_disconnect(
    client: mqtt.Client,
    userdata: dict,
    disconnect_flags,
    reason_code,
    properties,
) -> None:
    _mqtt_conn_state["connected"] = False


def _on_message(client: mqtt.Client, userdata: dict, msg: mqtt.MQTTMessage) -> None:
    """Parse incoming compact energy data and push to queue."""
    try:
        # Decode payload from bytes to string
        payload_str = msg.payload.decode("utf-8")
        
        # Parse the compact format
        reading = _parse_energy_reading(payload_str)
        if reading is None:
            print(f"Warning: Failed to parse MQTT message: {payload_str}")
            return
        
        # Push to queue for Streamlit
        _mqtt_queue.put_nowait(reading)
        
        # Save to InfluxDB
        try:
            influx_db.save_energy_reading(
                current_a=reading.get("current_A", 0.0),
                power_w=reading.get("power_W", 0.0),
                voltage_v=reading.get("voltage_V", 230.0),
                outlet_state=reading.get("outlet_state", "UNKNOWN")
            )
        except Exception as e:
            print(f"Error on InfluxDB layer: {e}")

    except (UnicodeDecodeError, Exception) as e:
        print(f"Error processing MQTT message: {e}")


# ---------------------------------------------------------------------------
# Connection helpers  (called from the Streamlit main thread)
# ---------------------------------------------------------------------------

def connect_mqtt(host: str, port: int, topic: str) -> None:
    """Tear down any existing connection and establish a fresh one."""
    existing: mqtt.Client | None = st.session_state.get("mqtt_client")
    if existing is not None:
        try:
            existing.loop_stop()
            existing.disconnect()
        except Exception:
            pass

    st.session_state.mqtt_messages = []
    _mqtt_conn_state["connected"] = False
    _mqtt_conn_state["error"] = ""

    # Drain stale messages from a previous session
    while not _mqtt_queue.empty():
        try:
            _mqtt_queue.get_nowait()
        except queue.Empty:
            break

    client = mqtt.Client(
        callback_api_version=CallbackAPIVersion.VERSION2,
        userdata={"topic": topic},
    )
    client.on_connect = _on_connect
    client.on_disconnect = _on_disconnect
    client.on_message = _on_message

    try:
        client.connect(host, port, keepalive=60)
        client.loop_start()
        st.session_state.mqtt_client = client
    except Exception as exc:
        _mqtt_conn_state["error"] = str(exc)
        st.session_state.mqtt_client = None


def disconnect_mqtt() -> None:
    """Stop the MQTT client and clear all buffered data."""
    client: mqtt.Client | None = st.session_state.get("mqtt_client")
    if client is not None:
        try:
            client.loop_stop()
            client.disconnect()
        except Exception:
            pass
    st.session_state.mqtt_client = None
    st.session_state.mqtt_messages = []
    _mqtt_conn_state["connected"] = False
    _mqtt_conn_state["error"] = ""

def publish_command(topic: str, payload: str) -> bool:
    """
    Publish the command into the specified topic. 
    Returns true if the command was send successfuly
    """
    client: mqtt.Client | None = st.session_state.get("mqtt_client")

    if client is not None and st.session_state.mqtt_connected:
        try:
            result = client.publish(topic, payload, qos=1)
            # result.rc == 0 means success
            return result.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception as e:
            st.error(f"Error publishing: {e}")
            return False
    return False

# ---------------------------------------------------------------------------
# Sync: thread boundary → session_state  (call at top of every rerun)
# ---------------------------------------------------------------------------

def sync_mqtt() -> None:
    """Pull connection flags and queued messages into session_state."""
    st.session_state.mqtt_connected = _mqtt_conn_state["connected"]
    st.session_state.mqtt_error = _mqtt_conn_state["error"]
    while not _mqtt_queue.empty():
        try:
            st.session_state.mqtt_messages.append(_mqtt_queue.get_nowait())
        except queue.Empty:
            break
    # Bound the buffer to prevent unbounded memory growth
    if len(st.session_state.mqtt_messages) > MAX_BUFFER_SIZE:
        st.session_state.mqtt_messages = st.session_state.mqtt_messages[-MAX_BUFFER_SIZE:]


def init_session_state() -> None:
    """Initialise MQTT-related session_state keys (idempotent)."""
    st.session_state.setdefault("mqtt_client", None)
    st.session_state.setdefault("mqtt_connected", False)
    st.session_state.setdefault("mqtt_error", "")
    st.session_state.setdefault("mqtt_messages", [])
