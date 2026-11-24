"""Shared fixtures and fakes for quart_app tests.

No test talks to a real Postgres, MQTT broker, or Home Assistant:
connections are replaced with the in-memory fakes below.
"""
import json

import pytest

import main


class FakePool:
    """Stands in for an asyncpg pool; returns canned rows from fetch()."""

    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    async def fetch(self, query, *args):
        self.calls.append((query, args))
        return self.rows


class FakeResponse:
    def __init__(self, status=200, body=""):
        self.status = status
        self._body = body if isinstance(body, str) else json.dumps(body)

    async def text(self):
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    """Stands in for aiohttp.ClientSession; records requests."""

    def __init__(self, status=200, body=None, error=None):
        self.status = status
        self.body = {} if body is None else body
        self.error = error
        self.requests = []

    def _request(self, method, url, **kwargs):
        self.requests.append({"method": method, "url": url, **kwargs})
        if self.error:
            raise self.error
        return FakeResponse(self.status, self.body)

    def post(self, url, **kwargs):
        return self._request("POST", url, **kwargs)

    def get(self, url, **kwargs):
        return self._request("GET", url, **kwargs)


@pytest.fixture
def app():
    main.app.config["TESTING"] = True
    main.app.config.pop("PG_POOL", None)
    yield main.app
    main.app.config.pop("PG_POOL", None)
    main.app.http_session = None


@pytest.fixture
def client(app):
    # test_client() does not run before_serving, so no DB or MQTT startup.
    return app.test_client()


@pytest.fixture
def pool(app):
    fake = FakePool()
    app.config["PG_POOL"] = fake
    return fake


@pytest.fixture
def capture_render(monkeypatch):
    """Replace render_template in a blueprint module and record its kwargs."""

    def _capture(module):
        captured = {}

        async def fake_render(template, **context):
            captured["template"] = template
            captured.update(context)
            return "rendered"

        monkeypatch.setattr(module, "render_template", fake_render)
        return captured

    return _capture
