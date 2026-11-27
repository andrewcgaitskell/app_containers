import json
import math
import os

import asyncpg
from quart import Blueprint, current_app, render_template, request

bp = Blueprint("temperature", __name__)

# DB Connection
DB_HOST = os.environ.get("POSTGRES_HOST", "localhost")
DB_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
DB_USER = os.environ.get("POSTGRES_USER", "mqttuser")
DB_PASS = os.environ.get("POSTGRES_PASSWORD", "mqttpassword")
DB_NAME = os.environ.get("POSTGRES_DB", "data")

MAX_POINTS = 500


async def get_pool():
    pool = current_app.config.get("PG_POOL")
    if pool is None:
        pool = await asyncpg.create_pool(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME,
            min_size=1,
            max_size=3,
        )
        current_app.config["PG_POOL"] = pool
    return pool


def extract_temperature(payload):
    """Return the temperature from a payload, whatever the key prefix is.

    Matches 'temperature' or any key ending '_temperature', e.g.
    'study_shellyhtg3_black_temperature'.
    """
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except ValueError:
            return None
    if not isinstance(payload, dict):
        return None
    for key, value in payload.items():
        if key == "temperature" or key.endswith("_temperature"):
            if isinstance(value, (int, float)):
                return float(value)
    return None


def get_hours():
    return max(1, min(request.args.get("hours", 24, type=int), 720))


async def render_temperature(topic, title, endpoint, endpoint_args, hours, target=None):
    """Chart the temperature readings stored for one MQTT topic."""
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT payload, received_at
        FROM "data".mqtt_messages
        WHERE topic = $1
          AND received_at >= now() - make_interval(hours => $2)
        ORDER BY received_at
        """,
        topic,
        hours,
    )

    points = []
    for row in rows:
        value = extract_temperature(row["payload"])
        if value is not None:
            points.append({"x": row["received_at"].isoformat(), "y": value})

    # Thin out long ranges so the browser isn't plotting thousands of points
    if len(points) > MAX_POINTS:
        step = math.ceil(len(points) / MAX_POINTS)
        thinned = points[::step]
        if thinned[-1] is not points[-1]:
            thinned.append(points[-1])
        points = thinned

    return await render_template(
        "temperature.html",
        device=title,
        endpoint=endpoint,
        endpoint_args=endpoint_args,
        target=target,
        hours=hours,
        points=points,
        latest=points[-1] if points else None,
    )


@bp.route("/temperature/<device>")
async def temperature(device):
    """Shelly devices, published to display/device/<device> by Home Assistant."""
    return await render_temperature(
        topic=f"display/device/{device}",
        title=device,
        endpoint="temperature.temperature",
        endpoint_args={"device": device},
        hours=get_hours(),
    )


@bp.route("/temperature/zigbee/<path:name>")
async def zigbee_temperature(name):
    """Zigbee2MQTT devices, published to zigbee2mqtt/<friendly name>.

    Optional ?target=22 draws a dashed setpoint line.
    """
    target = request.args.get("target", type=float)
    args = {"name": name}
    if target is not None:
        args["target"] = target
    return await render_temperature(
        topic=f"zigbee2mqtt/{name}",
        title=name,
        endpoint="temperature.zigbee_temperature",
        endpoint_args=args,
        hours=get_hours(),
        target=target,
    )


# In your app setup:
#   from temperature_plot import bp as temperature_bp
#   app.register_blueprint(temperature_bp)
# Then open /temperature/shellyhtg3_black?hours=24
# or /temperature/zigbee/Fermenting%20House%20Thermometer?target=22
