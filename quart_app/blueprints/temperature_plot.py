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


@bp.route("/temperature/<device>")
async def temperature(device):
    hours = max(1, min(request.args.get("hours", 24, type=int), 720))
    topic = f"display/device/{device}"

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
        device=device,
        hours=hours,
        points=points,
        latest=points[-1] if points else None,
    )


# In your app setup:
#   from temperature_plot import bp as temperature_bp
#   app.register_blueprint(temperature_bp)
# Then open /temperature/shellyhtg3_black?hours=24
