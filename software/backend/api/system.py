"""Liveness + stack health + admin audit."""

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from backend.api.helpers import admin_required
from backend.services import influx, mqtt_publisher, postgres

bp = Blueprint("system", __name__)


@bp.get("/admin/login-logs")
@admin_required
def login_logs():
    try:
        limit = min(max(int(request.args.get("limit", 100)), 1), 1000)
    except ValueError:
        limit = 100
    return {"logs": postgres.list_login_logs(limit)}


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
