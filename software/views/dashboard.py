"""
SMILE-IoT Dashboard

Thin UI orchestrator. Business logic lives in utils/:
  - utils/mqtt_client.py  → MQTT subscriber, callbacks, thread-safe sync

Run:  streamlit run app.py
"""

import time
import pandas as pd
import streamlit as st

from utils.mqtt_client import (
    connect_mqtt,
    disconnect_mqtt,
    init_session_state,
    sync_mqtt,
    publish_command,
)

# (Portugal)
GRID_VOLTAGE = 230.0

# ---------------------------------------------------------------------------
# Helpers (init Empty DataFrames)
# ---------------------------------------------------------------------------
def get_empty_rt_df():
    """Returns DataFrames with zeros for realtime graphs."""
    return pd.DataFrame({
        "timestamp": [pd.Timestamp.now()],
        "current_A": [0.0], # Ajustado para o nome da variável JSON do ESP32
        "power_W": [0.0],
        "outlet_state": ["OFF"]
    })

def get_empty_daily_df():
    """Placeholder for daiçy data until InfluxDB implementation."""
    return pd.DataFrame({
        "date": [pd.Timestamp.now().date()],
        "energy_kWh": [0.0],
        "cost_PT": [0.0]
    })

# ---------------------------------------------------------------------------
# Page config  (must be the first Streamlit command)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="SMILE-IoT Dashboard",
    page_icon=":material/electric_bolt:",
    layout="wide",
)

# Authentication guard
if not st.session_state.get("logged_in"):
    st.error("Authentication required. Please login.")
    st.stop()
else:
    # refresh last activity timestamp
    st.session_state.last_active = time.time()

# ---------------------------------------------------------------------------
# Boot sequence: init state → sync MQTT thread → ready
# ---------------------------------------------------------------------------
init_session_state()
sync_mqtt()

# ---------------------------------------------------------------------------
# Sidebar — global filters, MQTT controls & connection status
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## :material/electric_bolt: SMILE-IoT")
    st.caption("Local Energy Monitoring & Inspection System")
    st.markdown("---")
    
    st.markdown("### Broker Connection")
    mqtt_host  = st.text_input("Broker host", value="broker.emqx.io", key="sb_host")
    mqtt_port  = st.number_input("Broker port", value=1883, min_value=1, max_value=65535, key="sb_port")
    mqtt_topic = st.text_input("Topic", value="smile-iot/power", key="sb_topic")

    col_conn, col_disc = st.columns(2)
    with col_conn:
        if st.button("Connect", use_container_width=True, type="primary"):
            connect_mqtt(mqtt_host, int(mqtt_port), mqtt_topic)
            time.sleep(0.6)
            sync_mqtt()
            st.rerun()
    with col_disc:
        if st.button("Disconnect", use_container_width=True):
            disconnect_mqtt()
            st.rerun()

    # Connection state
    if st.session_state.mqtt_connected:
        st.success(":material/wifi: Connected to the Broker!")
    elif st.session_state.mqtt_error:
        st.error(f":material/wifi_off: Error: {st.session_state.mqtt_error}")
    else:
        st.warning(":material/wifi_off: Disconnected")

    st.caption(f"Messages in the buffer: {len(st.session_state.mqtt_messages)}")

    st.markdown("---")
    st.markdown("### View Configuration")
    history_window = st.selectbox(
        "Real time window",
        ["30 min", "60 min", "120 min"],
        index=1,
    )
    refresh_interval = st.slider("Auto-refresh (s)", min_value=2, max_value=30, value=5)
    
    st.markdown("---")
    st.caption("v0.3.0 — SMILE-IoT Live Data")

# ---------------------------------------------------------------------------
# Data resolution
# ---------------------------------------------------------------------------
rt_minutes = int(history_window.split()[0])

if st.session_state.mqtt_connected and len(st.session_state.mqtt_messages) > 0:
    msgs = st.session_state.mqtt_messages[-rt_minutes:] # Usa apenas as mensagens da janela definida
    rt_df = pd.DataFrame(msgs)
    
    # If there's no timestampin the Json create on when receiving
    if "timestamp" not in rt_df.columns:
        rt_df["timestamp"] = pd.Timestamp.now() 
    else:
        rt_df["timestamp"] = pd.to_datetime(rt_df["timestamp"])
        
    # Calculate Power (P = V * I) - assuming 230V
    if "current_A" in rt_df.columns:
        rt_df["power_W"] = rt_df["current_A"] * GRID_VOLTAGE
    else:
        rt_df["power_W"] = 0.0
else:
    rt_df = get_empty_rt_df()

daily_df = get_empty_daily_df() # History placeholder

# Extrat last values
latest = rt_df.iloc[-1]
prev = rt_df.iloc[-2] if len(rt_df) > 1 else latest

current_now = float(latest.get("current_A", 0.0))
power_now   = float(latest.get("power_W", 0.0))
avg_power   = float(rt_df["power_W"].mean())
max_power   = float(rt_df["power_W"].max())

delta_current = current_now - float(prev.get("current_A", 0.0))
delta_power   = power_now - float(prev.get("power_W", 0.0))


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title(":material/electric_bolt: SMILE-IoT energy dashboard")

_ts = latest["timestamp"]
_ts_str = _ts.strftime("%Y-%m-%d %H:%M:%S") if hasattr(_ts, "strftime") else str(_ts)
st.caption(
    f"Last reading: {_ts_str}  ·  Grid voltage: {GRID_VOLTAGE} V  ·  Sensor: SCT-013"
)

#---------------------------------------------------------------------------
# MQTT commands
#---------------------------------------------------------------------------
st.markdown("---")
col_info, col_ctrl = st.columns([2,1])

with col_info:
    st.subheader("Outlet State")
    #shows the current state based on the last message received by the board
    if "outlet_state" in latest:
        state = latest["outlet_state"]
        color = "green" if state == "ON" else "red"
        st.markdown(f"Outlet: **{color}[{state}]**")
    else:
        st.info("Waiting for data")

with col_ctrl:
    st.subheader("Remote commands")
    # we defined the reading topic in "power", so we replace it for the one defined on the board "command"
    cmd_topic = mqtt_topic.replace("power", "command")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("TURN ON", use_container_width=True, type="primary", disabled=not st.session_state.mqtt_connected):
            if publish_command(cmd_topic, "ON"):
                st.toast(f"Command 'ON' sent successfuly", icon="⚡")
            else:
                st.error("Failed sending command")

    with c2:
        if st.button("TURN OFF", use_container_width=True, disabled=not st.session_state.mqtt_connected):
            if publish_command(cmd_topic, "OFF"):
                st.toast(f"Command 'OFF' sent successfuly", icon="🔌")
            else:
                st.error("Failed sending command")

# ---------------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------------
with st.container(horizontal=True):
    st.metric(
        "Current (RMS)",
        f"{current_now:.2f} A",
        f"{delta_current:+.2f} A",
        border=True,
    )
    st.metric(
        "Instant power",
        f"{power_now:.0f} W",
        f"{delta_power:+.0f} W",
        border=True,
    )
    st.metric(
        f"Avg power ({rt_minutes} min)",
        f"{avg_power:.0f} W",
        border=True,
    )
    st.metric(
        "Peak power",
        f"{max_power:.0f} W",
        border=True,
    )

# ---------------------------------------------------------------------------
# Realtime charts
# ---------------------------------------------------------------------------
col_power, col_current = st.columns(2)

with col_power:
    with st.container(border=True):
        st.subheader("Power consumption (W)")
        st.area_chart(rt_df, x="timestamp", y="power_W", color="#2196F3")

with col_current:
    with st.container(border=True):
        st.subheader("Current draw (A)")
        st.line_chart(rt_df, x="timestamp", y="current_A", color="#FF9800")


# ---------------------------------------------------------------------------
# Auto-refresh
# ---------------------------------------------------------------------------
if st.session_state.mqtt_connected and refresh_interval:
    _refresh_ph = st.sidebar.empty()
    for _i in range(refresh_interval, 0, -1):
        _refresh_ph.caption(f":material/refresh: Updating in {_i}s…")
        time.sleep(1)
    _refresh_ph.empty()
    st.rerun()