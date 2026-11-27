import aiohttp
import pytest

from blueprints import hass
from conftest import FakeSession


@pytest.fixture
def on_pi(monkeypatch):
    """Quart's test client reports "<local>" as the client address; treat it as the Pi."""
    monkeypatch.setattr(hass, "LOCAL_ADDRS", hass.LOCAL_ADDRS | {"<local>"})


@pytest.fixture
def ha(app, monkeypatch, on_pi):
    """Configure a fake Home Assistant: placeholder token, fake URL, fake session."""
    monkeypatch.setattr(hass, "HASS_TOKEN", "test-token")
    monkeypatch.setattr(hass, "HASS_URL", "http://ha.test:8123/")
    session = FakeSession(status=200, body=[{"entity_id": "light.kitchen"}])
    app.http_session = session
    return session


async def test_set_light_on_calls_turn_on_with_options(client, ha):
    resp = await client.post(
        "/api/light/light.kitchen/set",
        json={"state": "ON", "brightness": 128, "ignored": 1},
    )

    assert resp.status_code == 200
    req = ha.requests[0]
    assert req["method"] == "POST"
    assert req["url"] == "http://ha.test:8123/api/services/light/turn_on"
    assert req["json"] == {"entity_id": "light.kitchen", "brightness": 128}
    assert req["headers"]["Authorization"] == "Bearer test-token"
    assert await resp.get_json() == [{"entity_id": "light.kitchen"}]


async def test_set_light_off_calls_turn_off(client, ha):
    resp = await client.post("/api/light/light.kitchen/set", json={"state": "off"})

    assert resp.status_code == 200
    assert ha.requests[0]["url"].endswith("/api/services/light/turn_off")


@pytest.mark.parametrize(
    "kwargs, error",
    [
        ({"json": {"state": "dim"}}, "state must be 'on' or 'off'"),
        ({"json": {"state": 1}}, "state must be 'on' or 'off'"),
        ({"json": {"state": None}}, "state must be 'on' or 'off'"),
        ({"json": {"brightness": 10}}, "missing 'state' in payload"),
        ({"json": ["state"]}, "missing 'state' in payload"),
        ({"data": "not json", "headers": {"Content-Type": "application/json"}}, "invalid json"),
    ],
)
async def test_set_light_rejects_bad_requests(client, ha, kwargs, error):
    resp = await client.post("/api/light/light.kitchen/set", **kwargs)

    assert resp.status_code == 400
    assert (await resp.get_json())["error"] == error
    assert ha.requests == []


async def test_missing_token_returns_500_without_calling_ha(client, ha, monkeypatch):
    monkeypatch.setattr(hass, "HASS_TOKEN", None)

    resp = await client.post("/api/light/light.kitchen/toggle")

    assert resp.status_code == 500
    assert "HASS_TOKEN" in (await resp.get_json())["error"]
    assert ha.requests == []


async def test_ha_connection_error_returns_500(client, app, monkeypatch, on_pi):
    monkeypatch.setattr(hass, "HASS_TOKEN", "test-token")
    app.http_session = FakeSession(error=aiohttp.ClientError("unreachable"))

    resp = await client.post("/api/light/light.kitchen/set", json={"state": "on"})

    assert resp.status_code == 500
    assert (await resp.get_json())["error"] == "failed to call Home Assistant"


async def test_toggle_passes_through_ha_status(client, ha):
    ha.status, ha.body = 401, "401: Unauthorized"

    resp = await client.post("/api/light/light.kitchen/toggle")

    assert resp.status_code == 401
    assert ha.requests[0]["url"].endswith("/api/services/light/toggle")
    assert await resp.get_json() == "401: Unauthorized"


async def test_get_state_returns_entity_json(client, ha):
    ha.body = {"entity_id": "light.kitchen", "state": "on"}

    resp = await client.get("/api/light/light.kitchen/get_state")

    assert resp.status_code == 200
    assert ha.requests[0]["method"] == "GET"
    assert ha.requests[0]["url"] == "http://ha.test:8123/api/states/light.kitchen"
    assert (await resp.get_json())["state"] == "on"


async def test_get_state_passes_through_errors(client, ha):
    ha.status, ha.body = 404, '{"message": "Entity not found."}'

    resp = await client.get("/api/light/light.missing/get_state")

    assert resp.status_code == 404
    assert await resp.get_data(as_text=True) == '{"message": "Entity not found."}'


async def test_light_ui_renders_entity(client, on_pi):
    resp = await client.get("/ui/light/light.kitchen")

    assert resp.status_code == 200
    assert resp.content_type.startswith("text/html")
    page = await resp.get_data(as_text=True)
    assert "Light: light.kitchen" in page
    assert 'const entity = "light.kitchen";' in page


@pytest.mark.parametrize(
    "path, raw, escaped_html, escaped_js",
    [
        (
            "%3Cscript%3Ealert(1)%3C/script%3E",
            "<script>alert(1)</script>",
            "Light: &lt;script&gt;alert(1)&lt;/script&gt;",
            r'const entity = "\u003cscript\u003ealert(1)\u003c/script\u003e";',
        ),
        (
            'x%22;alert(1);//',
            'x";alert(1);//',
            "Light: x&quot;;alert(1);//",
            r'const entity = "x\";alert(1);//";',
        ),
    ],
)
async def test_light_ui_escapes_entity_id(client, on_pi, path, raw, escaped_html, escaped_js):
    resp = await client.get(f"/ui/light/{path}")
    page = await resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert raw not in page
    assert escaped_html in page
    assert escaped_js in page


LAN = {"client": ("192.168.1.50", 50000)}


@pytest.mark.parametrize(
    "method, path",
    [
        ("POST", "/api/light/light.kitchen/set"),
        ("POST", "/api/light/light.kitchen/toggle"),
        ("GET", "/api/light/light.kitchen/get_state"),
        ("GET", "/ui/light/light.kitchen"),
    ],
)
async def test_light_routes_refuse_lan_clients(client, ha, method, path):
    resp = await client.open(path, method=method, json={"state": "on"}, scope_base=LAN)

    assert resp.status_code == 403
    assert ha.requests == []


async def test_test_client_address_is_not_trusted_by_default(client):
    assert "<local>" not in hass.LOCAL_ADDRS
    resp = await client.get("/api/light/light.kitchen/get_state")

    assert resp.status_code == 403


async def test_light_routes_allow_ipv6_localhost(client, ha):
    resp = await client.get(
        "/api/light/light.kitchen/get_state", scope_base={"client": ("::1", 50000)}
    )

    assert resp.status_code == 200
