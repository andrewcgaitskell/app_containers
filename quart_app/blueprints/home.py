from quart import Blueprint, render_template, url_for

from blueprints.temperature_plot import extract_temperature, get_pool

bp = Blueprint("home", __name__)

ZIGBEE_PREFIX = "zigbee2mqtt/"
SHELLY_PREFIX = "display/device/"

# Setpoint lines for charts linked from the landing page.
# Keep in step with the matching Home Assistant automation.
TARGETS = {
    "zigbee2mqtt/Fermenting House Thermometer": 22.0,  # "Fermenting House heater"
}


def chart_url(topic):
    """Return the chart URL for a temperature topic, or None if not chartable."""
    if topic.startswith(ZIGBEE_PREFIX):
        name = topic[len(ZIGBEE_PREFIX):]
        target = TARGETS.get(topic)
        if target is None:
            return url_for("temperature.zigbee_temperature", name=name)
        return url_for("temperature.zigbee_temperature", name=name, target=target)
    if topic.startswith(SHELLY_PREFIX):
        return url_for("temperature.temperature", device=topic[len(SHELLY_PREFIX):])
    return None


# Latest message per device topic that carried a temperature in the last day.
# CASE guards jsonb_object_keys, which fails on non-object payloads.
LATEST_SQL = r"""
    SELECT DISTINCT ON (topic) topic, payload, received_at
    FROM "data".mqtt_messages
    WHERE received_at >= now() - interval '24 hours'
      AND (topic LIKE 'zigbee2mqtt/%' OR topic LIKE 'display/device/%')
      AND CASE WHEN jsonb_typeof(payload) = 'object' THEN
            EXISTS (
              SELECT 1 FROM jsonb_object_keys(payload) AS k
              WHERE k = 'temperature'
                 OR (k LIKE '%\_temperature' AND k NOT LIKE '%device\_temperature')
            )
          ELSE false END
    ORDER BY topic, received_at DESC
"""


def split_topic(topic):
    """Return (name, source) for a chartable topic, or None for any other topic."""
    if topic.startswith(ZIGBEE_PREFIX):
        return topic[len(ZIGBEE_PREFIX):], "Zigbee"
    if topic.startswith(SHELLY_PREFIX):
        return topic[len(SHELLY_PREFIX):], "Shelly"
    return None


async def latest_sensors():
    """Latest temperature per sensor over the last day, sorted by name.

    Shared by the landing page and /api/sensors so both list the same rows.
    Each entry has topic, name, source, value (°C or None), target and
    received_at (datetime).
    """
    pool = await get_pool()
    rows = await pool.fetch(LATEST_SQL)

    sensors = []
    for row in rows:
        topic = row["topic"]
        parts = split_topic(topic)
        if parts is None:
            continue
        name, source = parts
        sensors.append(
            {
                "topic": topic,
                "name": name,
                "source": source,
                "value": extract_temperature(row["payload"]),
                "target": TARGETS.get(topic),
                "received_at": row["received_at"],
            }
        )
    sensors.sort(key=lambda s: s["name"].lower())
    return sensors


@bp.route("/")
async def index():
    sensors = [
        {
            "name": s["name"],
            "source": s["source"],
            "url": chart_url(s["topic"]),
            "value": s["value"],
            "target": s["target"],
            "seen": s["received_at"].isoformat(),
        }
        for s in await latest_sensors()
    ]
    return await render_template("home.html", sensors=sensors)
