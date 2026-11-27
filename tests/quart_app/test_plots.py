from datetime import datetime, timedelta, timezone

import pytest

from blueprints import presence_plot, temperature_plot

T0 = datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc)


def at(minutes):
    return T0 + timedelta(minutes=minutes)


# ---------------------------------------------------------------- temperature

@pytest.mark.parametrize(
    "payload, expected",
    [
        ({"temperature": 21.5}, 21.5),
        ({"study_shellyhtg3_black_temperature": 19}, 19.0),
        ('{"temperature": 18.25}', 18.25),
        ({"humidity": 40}, None),
        ({"temperature": "warm"}, None),
        ("not json", None),
        ([1, 2], None),
        (None, None),
    ],
)
def test_extract_temperature(payload, expected):
    assert temperature_plot.extract_temperature(payload) == expected


async def test_temperature_queries_device_topic_and_builds_points(client, pool, capture_render):
    ctx = capture_render(temperature_plot)
    pool.rows = [
        {"payload": {"temperature": 20.0}, "received_at": at(0)},
        {"payload": {"battery": 90}, "received_at": at(1)},
        {"payload": '{"x_temperature": 21}', "received_at": at(2)},
    ]

    resp = await client.get("/temperature/shelly1?hours=6")

    assert resp.status_code == 200
    _, args = pool.calls[0]
    assert args == ("display/device/shelly1", 6)
    assert ctx["template"] == "temperature.html"
    assert ctx["points"] == [
        {"x": at(0).isoformat(), "y": 20.0},
        {"x": at(2).isoformat(), "y": 21.0},
    ]
    assert ctx["latest"] == ctx["points"][-1]


@pytest.mark.parametrize("query, hours", [("", 24), ("?hours=0", 1), ("?hours=9999", 720), ("?hours=abc", 24)])
async def test_temperature_hours_is_clamped(client, pool, capture_render, query, hours):
    capture_render(temperature_plot)

    await client.get(f"/temperature/dev{query}")

    assert pool.calls[0][1][1] == hours


async def test_temperature_thins_long_series_and_keeps_last_point(client, pool, capture_render):
    ctx = capture_render(temperature_plot)
    pool.rows = [{"payload": {"temperature": i}, "received_at": at(i)} for i in range(1200)]

    await client.get("/temperature/dev")

    points = ctx["points"]
    assert len(points) <= temperature_plot.MAX_POINTS + 1
    assert points[0]["y"] == 0
    assert points[-1]["y"] == 1199


async def test_temperature_page_renders(client, pool):
    pool.rows = [{"payload": {"temperature": 20.0}, "received_at": at(0)}]

    resp = await client.get("/temperature/shelly1")
    html = await resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "shelly1" in html
    assert "20.0 °C" in html


async def test_temperature_page_renders_empty(client, pool):
    resp = await client.get("/temperature/shelly1")

    assert "No temperature readings" in await resp.get_data(as_text=True)


async def test_zigbee_temperature_queries_z2m_topic(client, pool, capture_render):
    ctx = capture_render(temperature_plot)
    pool.rows = [{"payload": {"temperature": 21.9, "battery": 100}, "received_at": at(0)}]

    resp = await client.get("/temperature/zigbee/Fermenting%20House%20Thermometer?hours=6&target=22")

    assert resp.status_code == 200
    assert pool.calls[0][1] == ("zigbee2mqtt/Fermenting House Thermometer", 6)
    assert ctx["device"] == "Fermenting House Thermometer"
    assert ctx["target"] == 22.0
    assert ctx["points"] == [{"x": at(0).isoformat(), "y": 21.9}]


async def test_zigbee_temperature_without_target(client, pool, capture_render):
    ctx = capture_render(temperature_plot)

    await client.get("/temperature/zigbee/Probe?target=abc")

    assert ctx["target"] is None
    assert ctx["endpoint_args"] == {"name": "Probe"}


async def test_zigbee_temperature_page_renders_target_and_range_links(client, pool):
    pool.rows = [{"payload": {"temperature": 21.9}, "received_at": at(0)}]

    resp = await client.get("/temperature/zigbee/Fermenting%20House%20Thermometer?target=22")
    html = await resp.get_data(as_text=True)

    assert "21.9 °C" in html
    assert "Target 22.0 °C" in html
    assert "const target = 22.0;" in html
    # Range links keep the device and the target line.
    assert "/temperature/zigbee/Fermenting%20House%20Thermometer?hours=168&amp;target=22.0" in html


async def test_shelly_page_has_no_target_line(client, pool):
    pool.rows = [{"payload": {"temperature": 20.0}, "received_at": at(0)}]

    html = await (await client.get("/temperature/shelly1")).get_data(as_text=True)

    assert "const target = null;" in html
    assert "Target" not in html
    assert "/temperature/shelly1?hours=168" in html


# ------------------------------------------------------------------- presence

async def test_presence_groups_events_by_device(client, pool, capture_render):
    ctx = capture_render(presence_plot)
    # Query returns newest first; the route re-sorts chronologically.
    pool.rows = [
        {"topic": "z2m/Presence_Kitchen", "received_at": at(5)},
        {"topic": "z2m/Presence_Hall", "received_at": at(3)},
        {"topic": "z2m/Presence_Kitchen", "received_at": at(1)},
    ]

    resp = await client.get("/presence?hours=48")

    assert resp.status_code == 200
    assert pool.calls[0][1] == (48, presence_plot.MAX_EVENTS)
    assert ctx["devices"] == ["z2m/Presence_Hall", "z2m/Presence_Kitchen"]
    assert ctx["event_count"] == 3
    assert ctx["datasets"] == [
        {"label": "z2m/Presence_Hall", "data": [{"x": at(3).isoformat(), "y": 0}]},
        {
            "label": "z2m/Presence_Kitchen",
            "data": [{"x": at(1).isoformat(), "y": 1}, {"x": at(5).isoformat(), "y": 1}],
        },
    ]


async def test_presence_page_renders(client, pool):
    pool.rows = [{"topic": "z2m/Presence_Hall", "received_at": at(0)}]

    resp = await client.get("/presence")

    assert resp.status_code == 200
    assert "z2m/Presence_Hall" in await resp.get_data(as_text=True)


async def test_presence_page_renders_empty(client, pool):
    resp = await client.get("/presence?hours=6")

    assert "No occupancy events in the last 6 hours" in await resp.get_data(as_text=True)


# --------------------------------------------------------------------- pools

@pytest.mark.parametrize("module", [temperature_plot, presence_plot])
async def test_get_pool_creates_once_and_caches(app, monkeypatch, module):
    created = []

    async def fake_create_pool(**kwargs):
        created.append(kwargs)
        return object()

    monkeypatch.setattr(module.asyncpg, "create_pool", fake_create_pool)

    async with app.app_context():
        first = await module.get_pool()
        second = await module.get_pool()

    assert first is second
    assert len(created) == 1
