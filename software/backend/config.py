"""Single source of configuration — reads software/.env once at import.

Every other module gets its settings from here; nothing else reads
os.environ directly. See .env.example for the full variable reference.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

SOFTWARE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(SOFTWARE_DIR / ".env")


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


# --- PostgreSQL --------------------------------------------------------------
POSTGRES = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": _int("DB_PORT", 5432),
    "dbname": os.environ.get("POSTGRES_DB", "smile_iot"),
    "user": os.environ.get("POSTGRES_USER", "smile"),
    "password": os.environ.get("POSTGRES_PASSWORD", ""),
}

# --- InfluxDB ----------------------------------------------------------------
INFLUX_URL = os.environ.get("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.environ.get("INFLUX_TOKEN", "")
INFLUX_ORG = os.environ.get("INFLUX_ORG", "smile_org")
INFLUX_BUCKET = os.environ.get("INFLUX_BUCKET", "energy_data")
INFLUX_MEASUREMENT = "energy_reading"

# --- MQTT (must match firmware/include/config.h) -----------------------------
MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = _int("MQTT_PORT", 1883)
MQTT_TOPIC_TELEMETRY = os.environ.get("MQTT_TOPIC_TELEMETRY", "smile-iot/power")
MQTT_TOPIC_COMMAND = os.environ.get("MQTT_TOPIC_COMMAND", "smile-iot/command")

# Tag applied to readings until the firmware sends a device id (single-board scope)
DEFAULT_DEVICE_TAG = "SCT-013_ESP32"

# --- API / auth ---------------------------------------------------------------
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "")
SESSION_TIMEOUT_MIN = _int("SESSION_TIMEOUT_MIN", 30)
MAX_FAILED_ATTEMPTS = _int("MAX_FAILED_ATTEMPTS", 5)
LOCKOUT_MINUTES = _int("LOCKOUT_MINUTES", 15)
COST_PER_KWH = _float("COST_PER_KWH", 0.25)

# --- SMTP (password reset) — empty SMTP_HOST disables sending -----------------
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = _int("SMTP_PORT", 587)
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
RESET_URL_BASE = os.environ.get("RESET_URL_BASE", "http://localhost:5173/login")
