"""Global app settings.

Currently just the grid voltage — the value used server-side to derive power
from measured current (there is no voltage sensor). Any user may read it (the
dashboard shows it); only admins may change it.
"""

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from backend import config
from backend.api.helpers import admin_required, err
from backend.services import postgres

bp = Blueprint("settings", __name__)


@bp.get("/grid-voltage")
@jwt_required()
def get_grid_voltage():
    return {"voltage_V": postgres.get_grid_voltage()}


@bp.put("/grid-voltage")
@admin_required
def set_grid_voltage():
    raw = (request.get_json(silent=True) or {}).get("voltage_V")
    try:
        volts = float(raw)
    except (TypeError, ValueError):
        return err(400, "invalid_voltage", "voltage_V must be a number.")
    if not (config.GRID_VOLTAGE_MIN_V <= volts <= config.GRID_VOLTAGE_MAX_V):
        return err(
            400, "invalid_voltage",
            f"voltage_V must be between {config.GRID_VOLTAGE_MIN_V:.0f} and "
            f"{config.GRID_VOLTAGE_MAX_V:.0f} V.",
        )
    postgres.set_grid_voltage(volts)
    return {"voltage_V": volts}
