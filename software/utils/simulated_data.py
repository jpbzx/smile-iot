"""
SMILE-IoT — Constants and data generation helpers.

Pure functions for simulated sensor data and shared constants.
No Streamlit imports here so this module can be unit-tested independently.
"""

import datetime
import math

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GRID_VOLTAGE = 230       # Typical EU grid voltage (V)
SENSOR_MAX_A = 30        # SCT-013-030 rated current
MAX_BUFFER_SIZE = 120    # Max MQTT messages retained in memory
COST_PER_KWH = 0.25     # € approximation


# ---------------------------------------------------------------------------
# Simulated data generators  (mocked values — demo purposes)
# ---------------------------------------------------------------------------

def generate_realtime_data(minutes: int = 60) -> pd.DataFrame:
    """Generate synthetic current/power readings as if coming from the ESP32."""
    now = datetime.datetime.now()
    timestamps = pd.date_range(end=now, periods=minutes, freq="min")
    np.random.seed(now.minute)

    base_current = 2.5 + 0.5 * np.sin(np.linspace(0, 4 * math.pi, minutes))
    noise = np.random.normal(0, 0.15, minutes)
    spikes = np.where(
        np.random.random(minutes) > 0.92,
        np.random.uniform(3, 8, minutes),
        0,
    )
    current_rms = np.clip(base_current + noise + spikes, 0.1, SENSOR_MAX_A)
    power_w = current_rms * GRID_VOLTAGE

    return pd.DataFrame({
        "timestamp": timestamps,
        "current_rms_A": np.round(current_rms, 3),
        "power_W": np.round(power_w, 2),
        "voltage_V": GRID_VOLTAGE,
    })


def generate_daily_data(days: int = 30) -> pd.DataFrame:
    """Generate daily energy consumption summary (kWh)."""
    today = datetime.date.today()
    dates = pd.date_range(end=today, periods=days, freq="D")
    np.random.seed(today.day)

    base_kwh = 3.5 + 1.2 * np.sin(np.linspace(0, 2 * math.pi, days))
    noise = np.random.normal(0, 0.4, days)
    kwh = np.clip(base_kwh + noise, 0.5, 12)

    return pd.DataFrame({
        "date": dates,
        "energy_kWh": np.round(kwh, 2),
        "cost_PT": np.round(kwh * COST_PER_KWH, 2),
    })


def zero_rt_df(minutes: int = 60) -> pd.DataFrame:
    """Return a zeroed-out realtime DataFrame (shown while waiting for MQTT data)."""
    now = datetime.datetime.now()
    timestamps = pd.date_range(end=now, periods=minutes, freq="min")
    return pd.DataFrame({
        "timestamp": timestamps,
        "current_rms_A": 0.0,
        "power_W": 0.0,
        "voltage_V": float(GRID_VOLTAGE),
    })
