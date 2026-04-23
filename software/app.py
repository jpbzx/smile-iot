"""
SMILE-IoT Dashboard — Entry point.

Thin UI orchestrator. Business logic lives in utils/:
  - utils/data.py         → constants, simulated data generators
  - utils/mqtt_client.py  → MQTT subscriber, callbacks, thread-safe sync

Run:  streamlit run app.py
"""

import time
import pandas as pd
import streamlit as st

from utils.simulated_data import (
    GRID_VOLTAGE,
    generate_daily_data,
    generate_realtime_data,
    zero_rt_df,
)
from utils.mqtt_client import (
    connect_mqtt,
    disconnect_mqtt,
    init_session_state,
    sync_mqtt,
)

# ---------------------------------------------------------------------------
# Page config  (must be the first Streamlit command)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="SMILE-IoT Dashboard",
    page_icon=":material/electric_bolt:",
    layout="wide",
)

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
    data_source = st.radio(
        "Data source",
        ["Simulated", "MQTT (live)"],
        index=0,
        help="Switch to MQTT when the ESP32 broker is running.",
    )

    if data_source == "MQTT (live)":
        mqtt_host  = st.text_input("Broker host", value="localhost",  key="sb_host")
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

        if st.session_state.mqtt_connected:
            st.success(":material/wifi: Connected!")
        elif st.session_state.mqtt_error:
            st.error(f":material/wifi_off: {st.session_state.mqtt_error}")
        else:
            st.warning(":material/wifi_off: Not connected")

        st.caption(f"Buffer: {len(st.session_state.mqtt_messages)} messages")

    st.markdown("---")
    history_window = st.selectbox(
        "Realtime window",
        ["30 min", "60 min", "120 min"],
        index=1,
    )
    daily_days = st.slider("Daily history (days)", min_value=7, max_value=90, value=30)

    if data_source == "MQTT (live)" and st.session_state.mqtt_connected:
        refresh_interval = st.slider("Auto-refresh (s)", min_value=2, max_value=30, value=5)
    else:
        refresh_interval = None

    st.markdown("---")
    st.caption("v0.2.0 — SMILE-IoT Prototype")

# ---------------------------------------------------------------------------
# Data resolution
# ---------------------------------------------------------------------------
rt_minutes = int(history_window.split()[0])
daily_df = generate_daily_data(daily_days)

if data_source == "Simulated":
    rt_df = generate_realtime_data(rt_minutes)
elif st.session_state.mqtt_connected and len(st.session_state.mqtt_messages) >= 2:
    msgs = st.session_state.mqtt_messages[-rt_minutes:]
    rt_df = pd.DataFrame(msgs)
    rt_df["timestamp"] = pd.to_datetime(rt_df["timestamp"])
    for col, default in [("current_rms_A", 0.0), ("power_W", 0.0), ("voltage_V", float(GRID_VOLTAGE))]:
        if col not in rt_df.columns:
            rt_df[col] = default
else:
    rt_df = zero_rt_df(rt_minutes)

latest = rt_df.iloc[-1]
prev   = rt_df.iloc[-2]

current_now      = float(latest["current_rms_A"])
power_now        = float(latest["power_W"])
avg_power        = float(rt_df["power_W"].mean())
max_power        = float(rt_df["power_W"].max())
total_kwh_today  = float(daily_df.iloc[-1]["energy_kWh"])
total_cost_today = float(daily_df.iloc[-1]["cost_PT"])

delta_current = current_now - float(prev["current_rms_A"])
delta_power   = power_now   - float(prev["power_W"])

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title(":material/electric_bolt: SMILE-IoT energy dashboard")

_ts = latest["timestamp"]
_ts_str = _ts.strftime("%Y-%m-%d %H:%M:%S") if hasattr(_ts, "strftime") else str(_ts)
st.caption(
    f"Last reading: {_ts_str}  ·  Grid voltage: {GRID_VOLTAGE} V  ·  Sensor: SCT-013-030"
)

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
    st.metric(
        "Energy today",
        f"{total_kwh_today:.2f} kWh",
        f"€ {total_cost_today:.2f}",
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
        st.line_chart(rt_df, x="timestamp", y="current_rms_A", color="#FF9800")

# ---------------------------------------------------------------------------
# Daily energy history
# ---------------------------------------------------------------------------
with st.container(border=True):
    st.subheader("Daily energy consumption")
    col_bar, col_cost = st.columns([3, 1])
    with col_bar:
        st.bar_chart(daily_df, x="date", y="energy_kWh", color="#4CAF50")
    with col_cost:
        st.dataframe(
            daily_df.sort_values("date", ascending=False).head(10),
            column_config={
                "date": st.column_config.DateColumn("Date", format="MMM DD"),
                "energy_kWh": st.column_config.NumberColumn("Energy", format="%.2f kWh"),
                "cost_PT": st.column_config.NumberColumn("Cost", format="€ %.2f"),
            },
            hide_index=True,
            use_container_width=True,
        )

# ---------------------------------------------------------------------------
# Auto-refresh — only active when MQTT mode is connected
# ---------------------------------------------------------------------------
if data_source == "MQTT (live)" and st.session_state.mqtt_connected and refresh_interval:
    _refresh_ph = st.sidebar.empty()
    for _i in range(refresh_interval, 0, -1):
        _refresh_ph.caption(f":material/refresh: Refreshing in {_i}s…")
        time.sleep(1)
    _refresh_ph.empty()
    st.rerun()