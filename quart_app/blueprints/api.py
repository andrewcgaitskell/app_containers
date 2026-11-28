"""Read-only JSON temperature API, for the M5Stack Tab5 display.

The Tab5 has no MQTT or Postgres access, so it reads the same data as the
charts over HTTP. Like the charts, these routes are open to the LAN. They
only read: no writes, no light control (the light routes in hass.py are a
separate blueprint and stay Pi-only).

GET /api/sensors
    {"sensors": [{"name", "source", "value", "target", "seen", "history"}]}
    Latest reading per sensor in the last 24 h (the landing page's rows),
    sorted by name. value is °C to 2 dp or null, target is the setpoint
    or null, seen is unix epoch seconds (UTC), history is the relative
    URL of the sensor's /api/temperature/... endpoint.

GET /api/temperature/zigbee/<path:name>?hours=24&points=300
GET /api/temperature/shelly/<device>?hours=24&points=300
    {"name", "hours", "target", "latest", "points"}
    points is [[epoch seconds UTC, °C to 2 dp], ...], oldest first.
    hours is clamped to 1-720 (default 24). points is clamped to 10-1000
    (default 300); longer series are thinned to at most points + 1, always
    keeping the newest reading. latest is the last point, or null when
    there is no data (points is then []). target comes from home.TARGETS;
    the HTML chart's ?target= parameter is deliberately not used here.
    An unknown name returns 200 with no data, like the HTML charts.

Responses carry Cache-Control: max-age=30, so poll at 30-60 s.
"""
from quart import Blueprint, jsonify, request, url_for

from blueprints.home import SHELLY_PREFIX, TARGETS, ZIGBEE_PREFIX, latest_sensors
from blueprints.temperature_plot import (
    HISTORY_SQL,
    extract_temperature,
    get_hours,
    get_pool,
    thin,
)

bp = Blueprint("api", __name__, url_prefix="/api")

DEFAULT_POINTS = 300
MIN_POINTS = 10
MAX_POINTS = 1000
CACHE_SECONDS = 30


def get_points():
    return max(MIN_POINTS, min(request.args.get("points", DEFAULT_POINTS, type=int), MAX_POINTS))


def as_json(body):
    resp = jsonify(body)
    resp.headers["Cache-Control"] = f"max-age={CACHE_SECONDS}"
    return resp


def round_temp(value):
    return None if value is None else round(value, 2)


def history_url(source, name):
    if source == "Zigbee":
        return url_for("api.zigbee_temperature", name=name)
    return url_for("api.shelly_temperature", device=name)


@bp.route("/sensors")
async def sensors():
    return as_json(
        {
            "sensors": [
                {
                    "name": s["name"],
                    "source": s["source"],
                    "value": round_temp(s["value"]),
                    "target": s["target"],
                    "seen": int(s["received_at"].timestamp()),
                    "history": history_url(s["source"], s["name"]),
                }
                for s in await latest_sensors()
            ]
        }
    )


async def history(topic, name):
    """Temperature series for one topic, as the JSON described above."""
    hours = get_hours()
    pool = await get_pool()
    rows = await pool.fetch(HISTORY_SQL, topic, hours)

    # Drop payloads without a temperature before thinning, so no gaps appear.
    points = []
    for row in rows:
        value = extract_temperature(row["payload"])
        if value is not None:
            points.append([int(row["received_at"].timestamp()), round(value, 2)])
    points = thin(points, get_points())

    return as_json(
        {
            "name": name,
            "hours": hours,
            "target": TARGETS.get(topic),
            "latest": points[-1] if points else None,
            "points": points,
        }
    )


@bp.route("/temperature/zigbee/<path:name>")
async def zigbee_temperature(name):
    return await history(f"{ZIGBEE_PREFIX}{name}", name)


@bp.route("/temperature/shelly/<device>")
async def shelly_temperature(device):
    return await history(f"{SHELLY_PREFIX}{device}", device)
