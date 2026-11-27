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


@bp.route("/")
async def index():
    pool = await get_pool()
    # Latest message per device topic that carried a temperature in the last day.
    # CASE guards jsonb_object_keys, which fails on non-object payloads.
    rows = await pool.fetch(
        r"""
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
    )

    sensors = []
    for row in rows:
        topic = row["topic"]
        url = chart_url(topic)
        if url is None:
            continue
        zigbee = topic.startswith(ZIGBEE_PREFIX)
        prefix = ZIGBEE_PREFIX if zigbee else SHELLY_PREFIX
        sensors.append(
            {
                "name": topic[len(prefix):],
                "source": "Zigbee" if zigbee else "Shelly",
                "url": url,
                "value": extract_temperature(row["payload"]),
                "target": TARGETS.get(topic),
                "seen": row["received_at"].isoformat(),
            }
        )
    sensors.sort(key=lambda s: s["name"].lower())

    return await render_template("home.html", sensors=sensors)
