from datetime import datetime, timezone

import pytest

from blueprints import home

T0 = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)
LAN = {"client": ("192.168.1.50", 50000)}


def row(topic, payload):
    return {"topic": topic, "payload": payload, "received_at": T0}


async def test_home_lists_temperature_devices_with_chart_links(client, pool, capture_render):
    ctx = capture_render(home)
    pool.rows = [
        row("zigbee2mqtt/Fermenting House Thermometer", {"temperature": 21.9, "battery": 100}),
        row("display/device/shellyhtg3_black", {"temperature": 19.5}),
        row("zigbee2mqtt/bedroom probe", {"temperature": 18}),
        row("somewhere/else", {"temperature": 1}),
    ]

    resp = await client.get("/")

    assert resp.status_code == 200
    _, args = pool.calls[0]
    assert args == ()
    assert ctx["template"] == "home.html"
    assert [(s["name"], s["source"], s["url"], s["value"], s["target"]) for s in ctx["sensors"]] == [
        ("bedroom probe", "Zigbee", "/temperature/zigbee/bedroom%20probe", 18.0, None),
        (
            "Fermenting House Thermometer",
            "Zigbee",
            "/temperature/zigbee/Fermenting%20House%20Thermometer?target=22.0",
            21.9,
            22.0,
        ),
        ("shellyhtg3_black", "Shelly", "/temperature/shellyhtg3_black", 19.5, None),
    ]
    assert ctx["sensors"][0]["seen"] == T0.isoformat()


async def test_home_query_skips_device_temperature_and_guards_scalars(client, pool, capture_render):
    capture_render(home)

    await client.get("/")

    query, _ = pool.calls[0]
    assert "jsonb_typeof(payload) = 'object'" in query
    assert "device\\_temperature" in query
    assert "interval '24 hours'" in query


async def test_home_page_renders(client, pool):
    pool.rows = [row("zigbee2mqtt/Fermenting House Thermometer", {"temperature": 21.94})]

    html = await (await client.get("/")).get_data(as_text=True)

    assert "Fermenting House Thermometer" in html
    assert "21.9 °C" in html
    assert "target 22.0 °C" in html
    assert 'href="/temperature/zigbee/Fermenting%20House%20Thermometer?target=22.0"' in html
    assert 'href="/presence"' in html


async def test_home_page_renders_empty(client, pool):
    html = await (await client.get("/")).get_data(as_text=True)

    assert "No device has reported a temperature" in html
    assert 'href="/presence"' in html


@pytest.mark.parametrize("path", ["/", "/temperature/zigbee/Probe", "/presence", "/status"])
async def test_charts_are_open_to_lan_clients(client, pool, path):
    resp = await client.get(path, scope_base=LAN)

    assert resp.status_code == 200
