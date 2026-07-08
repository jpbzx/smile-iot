"""Relay control — publishes the firmware's plain-text command contract
(ON / OFF / RESET on smile-iot/command, QoS 1).

202, not 200: delivery to the ESP32 is asynchronous. The UI confirms by
watching outlet_state / trip_latched change in /api/telemetry/latest.
"""

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from backend.api.helpers import err
from backend.services import mqtt_publisher

bp = Blueprint("control", __name__)


@bp.post("/outlet")
@jwt_required()
def outlet():
    state = ((request.get_json(silent=True) or {}).get("state") or "").upper()
    if state not in ("ON", "OFF"):
        return err(400, "invalid_state", "state must be 'ON' or 'OFF'.")
    if not mqtt_publisher.publish_command(state):
        return err(503, "broker_unavailable", "Could not publish to the MQTT broker.")
    return {"published": True, "command": state}, 202


@bp.post("/reset-trip")
@jwt_required()
def reset_trip():
    if not mqtt_publisher.publish_command("RESET"):
        return err(503, "broker_unavailable", "Could not publish to the MQTT broker.")
    return {"published": True, "command": "RESET"}, 202
