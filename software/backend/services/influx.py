"""InfluxDB read path for the API.

Writes happen only in backend/ingest/worker.py; the API reads. The two
processes share no memory — the bucket is the interface, so "latest
reading" is simply the newest point.
"""

import re
from datetime import datetime, timezone

from influxdb_client import InfluxDBClient

from backend import config

_client: InfluxDBClient | None = None

_EVERY_RE = re.compile(r"^\d{1,4}[smh]$")  # e.g. 10s, 5m, 1h


def _get_client() -> InfluxDBClient:
    global _client
    if _client is None:
        _client = InfluxDBClient(
            url=config.INFLUX_URL, token=config.INFLUX_TOKEN, org=config.INFLUX_ORG
        )
    return _client


def ping() -> bool:
    try:
        return _get_client().ping()
    except Exception:
        return False


def latest() -> dict | None:
    """Newest reading (all fields pivoted into one row), or None if the
    bucket has no point in the last 5 minutes (device considered offline)."""
    flux = f'''
        from(bucket: "{config.INFLUX_BUCKET}")
          |> range(start: -5m)
          |> filter(fn: (r) => r._measurement == "{config.INFLUX_MEASUREMENT}")
          |> last()
          |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> sort(columns: ["_time"], desc: true)
          |> limit(n: 1)
    '''
    tables = _get_client().query_api().query(flux)
    for table in tables:
        for rec in table.records:
            v = rec.values
            return {
                "timestamp": rec.get_time().isoformat(),
                "current_A": v.get("current_A"),
                "power_W": v.get("power_W"),
                "voltage_V": v.get("voltage_V"),
                "outlet_state": v.get("outlet_state"),
                "trip_latched": bool(v.get("trip_latched", 0)),
            }
    return None


def range_series(minutes: int, every: str = "10s") -> list[dict]:
    """Downsampled current/power series for charts."""
    if not _EVERY_RE.match(every):
        raise ValueError("bad 'every' window")
    flux = f'''
        from(bucket: "{config.INFLUX_BUCKET}")
          |> range(start: -{int(minutes)}m)
          |> filter(fn: (r) => r._measurement == "{config.INFLUX_MEASUREMENT}")
          |> filter(fn: (r) => r._field == "current_A" or r._field == "power_W")
          |> aggregateWindow(every: {every}, fn: mean, createEmpty: false)
          |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> sort(columns: ["_time"])
    '''
    points = []
    for table in _get_client().query_api().query(flux):
        for rec in table.records:
            points.append({
                "t": rec.get_time().isoformat(),
                "current_A": rec.values.get("current_A"),
                "power_W": rec.values.get("power_W"),
            })
    return points


def daily(days: int) -> list[dict]:
    """Daily energy (kWh) and cost. mean(power) × 24 h is a fair
    approximation at the firmware's fixed 1 Hz cadence; switch to
    integral() if the cadence ever becomes irregular."""
    flux = f'''
        from(bucket: "{config.INFLUX_BUCKET}")
          |> range(start: -{int(days)}d)
          |> filter(fn: (r) => r._measurement == "{config.INFLUX_MEASUREMENT}")
          |> filter(fn: (r) => r._field == "power_W")
          |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
          |> sort(columns: ["_time"])
    '''
    out = []
    for table in _get_client().query_api().query(flux):
        for rec in table.records:
            mean_w = rec.get_value()
            if mean_w is None:
                continue
            kwh = round(mean_w * 24.0 / 1000.0, 3)
            out.append({
                "date": rec.get_time().date().isoformat(),
                "energy_kWh": kwh,
                "cost_eur": round(kwh * config.COST_PER_KWH, 2),
            })
    return out


def last_reading_age_s() -> float | None:
    """Seconds since the newest point (device liveness), None if no data."""
    flux = f'''
        from(bucket: "{config.INFLUX_BUCKET}")
          |> range(start: -24h)
          |> filter(fn: (r) => r._measurement == "{config.INFLUX_MEASUREMENT}")
          |> filter(fn: (r) => r._field == "current_A")
          |> last()
    '''
    for table in _get_client().query_api().query(flux):
        for rec in table.records:
            return round((datetime.now(timezone.utc) - rec.get_time()).total_seconds(), 1)
    return None
