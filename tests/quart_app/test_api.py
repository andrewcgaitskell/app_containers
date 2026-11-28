from datetime import datetime, timedelta, timezone

import pytest

from blueprints import api, home, temperature_plot

T0 = datetime(2026, 11, 28, 12, 0, tzinfo=timezone.utc)
EPOCH0 = int(T0.timestamp())
LAN = {"client": ("192.168.1.50", 50000)}


def at(minutes):
    return T0 + timedelta(minutes=minutes)


def latest_row(topic, payload):
    return {"topic": topic, "payload": payload, "received_at": T0}


def history_row(minutes, payload):
    return {"payload": payload, "received_at": at(minutes)}


# ------------------------------------------------------------------ /sensors

async def test_sensors_lists_latest_reading_per_sensor(client, pool):
    pool.rows = [
        latest_row("zigbee2mqtt/Fermenting House Thermometer", {"temperature": 21.944, "battery": 100}),
        latest_row("display/device/shellyhtg3_black", {"study_temperature": 19.5}),
        latest_row("zigbee2mqtt/bedroom probe", {"temperature": 18}),
        latest_row("somewhere/else", {"temperature": 1}),
    ]

    resp = await client.get("/api/sensors")

    assert resp.status_code == 200
    assert resp.headers["Cache-Control"] == "max-age=30"
    query, args = pool.calls[0]
    assert query == home.LATEST_SQL
    assert args == ()
    assert (await resp.get_json())["sensors"] == [
        {
            "name": "bedroom probe",
            "source": "Zigbee",
            "value": 18.0,
            "target": None,
            "seen": EPOCH0,
            "history": "/api/temperature/zigbee/bedroom%20probe",
        },
        {
            "name": "Fermenting House Thermometer",
            "source": "Zigbee",
            "value": 21.94,
            "target": 22.0,
            "seen": EPOCH0,
            "history": "/api/temperature/zigbee/Fermenting%20House%20Thermometer",
        },
        {
            "name": "shellyhtg3_black",
            "source": "Shelly",
            "value": 19.5,
            "target": None,
            "seen": EPOCH0,
            "history": "/api/temperature/shelly/shellyhtg3_black",
        },
    ]


async def test_sensors_seen_is_integer_epoch(client, pool):
    pool.rows = [latest_row("zigbee2mqtt/Probe", {"temperature": 20})]

    sensor = (await (await client.get("/api/sensors")).get_json())["sensors"][0]

    assert isinstance(sensor["seen"], int)


async def test_sensors_empty(client, pool):
    resp = await client.get("/api/sensors")

    assert (await resp.get_json()) == {"sensors": []}


async def test_sensors_match_landing_page(client, pool, capture_render):
    ctx = capture_render(home)
    pool.rows = [
        latest_row("zigbee2mqtt/b", {"temperature": 1}),
        latest_row("display/device/a", {"temperature": 2}),
        latest_row("other/c", {"temperature": 3}),
    ]

    await client.get("/")
    api_names = [s["name"] for s in (await (await client.get("/api/sensors")).get_json())["sensors"]]

    assert api_names == [s["name"] for s in ctx["sensors"]] == ["a", "b"]


# ------------------------------------------------------------ history routes

async def test_zigbee_history_queries_topic_and_builds_points(client, pool):
    pool.rows = [
        history_row(0, {"temperature": 21.456}),
        history_row(5, {"battery": 90}),
        history_row(10, {"temperature": 22}),
    ]

    resp = await client.get("/api/temperature/zigbee/Fermenting%20House%20Thermometer?hours=6")

    assert resp.status_code == 200
    assert resp.headers["Cache-Control"] == "max-age=30"
    query, args = pool.calls[0]
    assert query == temperature_plot.HISTORY_SQL
    assert args == ("zigbee2mqtt/Fermenting House Thermometer", 6)
    body = await resp.get_json()
    assert body == {
        "name": "Fermenting House Thermometer",
        "hours": 6,
        "target": 22.0,
        "latest": [EPOCH0 + 600, 22.0],
        "points": [[EPOCH0, 21.46], [EPOCH0 + 600, 22.0]],
    }
    assert all(isinstance(t, int) for t, _ in body["points"])


async def test_zigbee_history_ignores_target_query(client, pool):
    resp = await client.get("/api/temperature/zigbee/Probe?target=30")

    assert (await resp.get_json())["target"] is None


async def test_shelly_history_queries_device_topic(client, pool):
    pool.rows = [history_row(0, {"study_temperature": 19.5})]

    body = await (await client.get("/api/temperature/shelly/shellyhtg3_black")).get_json()

    assert pool.calls[0][1] == ("display/device/shellyhtg3_black", 24)
    assert body["name"] == "shellyhtg3_black"
    assert body["target"] is None
    assert body["points"] == [[EPOCH0, 19.5]]


async def test_history_no_data(client, pool):
    body = await (await client.get("/api/temperature/zigbee/Nobody")).get_json()

    assert body == {"name": "Nobody", "hours": 24, "target": None, "latest": None, "points": []}


@pytest.mark.parametrize("query, hours", [("", 24), ("?hours=0", 1), ("?hours=9999", 720), ("?hours=abc", 24)])
async def test_history_hours_is_clamped(client, pool, query, hours):
    body = await (await client.get(f"/api/temperature/shelly/dev{query}")).get_json()

    assert pool.calls[0][1][1] == hours
    assert body["hours"] == hours


@pytest.mark.parametrize(
    "query, limit",
    [("", 300), ("?points=1", 10), ("?points=99999", 1000), ("?points=abc", 300), ("?points=50", 50)],
)
async def test_history_points_is_clamped(client, pool, query, limit):
    pool.rows = [history_row(i, {"temperature": i}) for i in range(5000)]

    points = (await (await client.get(f"/api/temperature/shelly/dev{query}")).get_json())["points"]

    assert len(points) <= limit + 1


async def test_history_thins_long_series_and_keeps_last_point(client, pool):
    pool.rows = [history_row(i, {"temperature": i}) for i in range(1200)]

    body = await (await client.get("/api/temperature/shelly/dev")).get_json()

    points = body["points"]
    assert len(points) <= 301
    assert points[0] == [EPOCH0, 0]
    assert points[-1] == [EPOCH0 + 1199 * 60, 1199]
    assert body["latest"] == points[-1]


async def test_history_drops_empty_payloads_before_thinning(client, pool):
    # Every other row has no temperature; after dropping them 300 remain,
    # which fits the default limit, so nothing should be thinned away.
    pool.rows = [
        history_row(i, {"temperature": i} if i % 2 == 0 else {"battery": 1}) for i in range(600)
    ]

    points = (await (await client.get("/api/temperature/shelly/dev")).get_json())["points"]

    assert len(points) == 300


# ------------------------------------------------------------- access rules

@pytest.mark.parametrize(
    "path", ["/api/sensors", "/api/temperature/zigbee/Probe", "/api/temperature/shelly/dev"]
)
async def test_api_is_open_to_lan_clients(client, pool, path):
    resp = await client.get(path, scope_base=LAN)

    assert resp.status_code == 200


@pytest.mark.parametrize(
    "path", ["/api/sensors", "/api/temperature/zigbee/Probe", "/api/temperature/shelly/dev"]
)
async def test_api_is_read_only(client, pool, path):
    resp = await client.post(path)

    assert resp.status_code == 405


async def test_light_api_stays_pi_only(client):
    resp = await client.get("/api/light/light.kitchen/get_state", scope_base=LAN)

    assert resp.status_code == 403


# ------------------------------------------------------------------- thin()

def test_thin_leaves_short_series_alone():
    points = [[i, i] for i in range(10)]

    assert temperature_plot.thin(points, 10) is points


def test_thin_keeps_first_and_last():
    points = [[i, i] for i in range(1000)]

    thinned = temperature_plot.thin(points, 300)

    assert len(thinned) <= 301
    assert thinned[0] == [0, 0]
    assert thinned[-1] == [999, 999]


def test_api_points_constants():
    assert (api.MIN_POINTS, api.DEFAULT_POINTS, api.MAX_POINTS) == (10, 300, 1000)
