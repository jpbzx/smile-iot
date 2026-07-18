"""Telemetry reads — everything comes from InfluxDB (written by the
ingest worker; the API never touches MQTT for inbound data)."""

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from backend.api.helpers import err
from backend.services import influx

bp = Blueprint("telemetry", __name__)


@bp.get("/latest")
@jwt_required()
def latest():
    reading = influx.latest()
    if reading is None:
        return "", 204  # no data in the last 5 min → device offline
    return reading


@bp.get("/range")
@jwt_required()
def range_():
    try:
        minutes = min(max(int(request.args.get("minutes", 60)), 1), 1440)
        every = request.args.get("every", "10s")
        points = influx.range_series(minutes, every)
    except ValueError:
        return err(400, "bad_params", "minutes must be an int, every like '10s'/'1m'.")
    return {"minutes": minutes, "every": every, "points": points}


@bp.get("/daily")
@jwt_required()
def daily():
    try:
        days = min(max(int(request.args.get("days", 30)), 1), 365)
    except ValueError:
        return err(400, "bad_params", "days must be an int.")
    return {"days": influx.daily(days)}
