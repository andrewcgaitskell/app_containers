import os

import asyncpg
from quart import Blueprint, current_app, render_template, request

bp = Blueprint("presence", __name__)

DB_HOST = os.environ.get("POSTGRES_HOST", "localhost")
DB_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
DB_USER = os.environ.get("POSTGRES_USER", "mqttuser")
DB_PASS = os.environ.get("POSTGRES_PASSWORD", "mqttpassword")
DB_NAME = os.environ.get("POSTGRES_DB", "data")
MAX_EVENTS = 5000


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


@bp.route("/presence")
async def presence_events():
    hours = max(1, min(request.args.get("hours", 24, type=int), 720))
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT topic, received_at
        FROM "data".mqtt_messages
        WHERE topic LIKE '%Presence%'
          AND payload->'occupancy' = 'true'::jsonb
          AND received_at >= now() - make_interval(hours => $1)
        ORDER BY received_at DESC
        LIMIT $2
        """,
        hours,
        MAX_EVENTS,
    )

    # The query limits the newest events; sort those chronologically for plotting.
    rows = sorted(rows, key=lambda row: row["received_at"])
    devices = sorted({row["topic"] for row in rows})
    lane_by_topic = {topic: index for index, topic in enumerate(devices)}

    datasets = [
        {
            "label": topic,
            "data": [
                {"x": row["received_at"].isoformat(), "y": lane_by_topic[topic]}
                for row in rows
                if row["topic"] == topic
            ],
        }
        for topic in devices
    ]

    return await render_template(
        "presence.html",
        hours=hours,
        devices=devices,
        datasets=datasets,
        event_count=len(rows),
    )

