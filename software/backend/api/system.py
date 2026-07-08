"""Liveness + stack health."""

from flask import Blueprint
from flask_jwt_extended import jwt_required

from backend.services import influx, mqtt_publisher, postgres

bp = Blueprint("system", __name__)


@bp.get("/health")
def health():
    return {"status": "ok"}


@bp.get("/system/status")
@jwt_required()
def status():
    return {
        "postgres_ok": postgres.ping(),
        "influx_ok": influx.ping(),
        "mqtt_connected": mqtt_publisher.check_connection(),
        "last_reading_age_s": influx.last_reading_age_s(),
    }
