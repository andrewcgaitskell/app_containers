import json

import main


class FakeConn:
    def __init__(self, exists=1):
        self.exists = exists
        self.executed = []
        self.closed = False

    async def fetchval(self, query, *args):
        return self.exists

    async def execute(self, query, *args):
        self.executed.append((" ".join(query.split()), args))

    async def close(self):
        self.closed = True


def fake_connect(conns, calls):
    async def _connect(**kwargs):
        calls.append(kwargs)
        return conns.pop(0)

    return _connect


async def test_status(client):
    resp = await client.get("/status")
    assert resp.status_code == 200
    assert await resp.get_json() == {"status": "MQTT listener running"}


async def test_write_message_inserts_json_payload(monkeypatch):
    conn = FakeConn()
    calls = []
    monkeypatch.setattr(main.asyncpg, "connect", fake_connect([conn], calls))

    await main.write_message("home/temp", 1, False, {"temperature": 21.5})

    assert calls[0]["database"] == "data"
    query, args = conn.executed[0]
    assert "INSERT INTO data.mqtt_messages" in query
    assert args == ("home/temp", 1, False, json.dumps({"temperature": 21.5}))
    assert conn.closed


async def test_write_message_swallows_db_errors(monkeypatch, caplog):
    async def broken_connect(**kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(main.asyncpg, "connect", broken_connect)

    await main.write_message("t", 0, False, {})  # must not raise

    assert "Error writing message to DB" in caplog.text


async def test_init_db_creates_database_when_missing(monkeypatch):
    sys_conn, data_conn = FakeConn(exists=None), FakeConn()
    calls = []
    monkeypatch.setattr(main.asyncpg, "connect", fake_connect([sys_conn, data_conn], calls))

    await main.init_db()

    assert [c["database"] for c in calls] == ["postgres", "data"]
    assert ("CREATE DATABASE data;", ()) in sys_conn.executed
    data_sql = " ".join(q for q, _ in data_conn.executed)
    assert "CREATE SCHEMA IF NOT EXISTS data" in data_sql
    assert "CREATE TABLE IF NOT EXISTS data.mqtt_messages" in data_sql
    assert sys_conn.closed and data_conn.closed


async def test_init_db_skips_create_when_database_exists(monkeypatch):
    sys_conn, data_conn = FakeConn(exists=1), FakeConn()
    monkeypatch.setattr(main.asyncpg, "connect", fake_connect([sys_conn, data_conn], []))

    await main.init_db()

    assert sys_conn.executed == []


class FakeMessage:
    def __init__(self, topic, payload, qos=0, retain=False):
        self.topic = topic
        self.payload = payload
        self.qos = qos
        self.retain = retain


class FakeMqttClient:
    def __init__(self, messages):
        self._messages = messages
        self.subscribed = []

    def __call__(self, host, port):
        self.host, self.port = host, port
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def subscribe(self, topic):
        self.subscribed.append(topic)

    @property
    def messages(self):
        async def gen():
            for m in self._messages:
                yield m

        return gen()


async def test_mqtt_listener_decodes_json_and_falls_back_to_raw(monkeypatch):
    fake_client = FakeMqttClient([
        FakeMessage("sensor/a", b'{"temperature": 20}', qos=1, retain=True),
        FakeMessage("sensor/b", b"not json"),
    ])
    written = []

    async def record(**kwargs):
        written.append(kwargs)

    monkeypatch.setattr(main, "Client", fake_client)
    monkeypatch.setattr(main, "write_message", record)

    await main.mqtt_listener()

    assert fake_client.subscribed == [main.MQTT_TOPIC]
    assert written == [
        {"topic": "sensor/a", "qos": 1, "retain": True, "payload": {"temperature": 20}},
        {"topic": "sensor/b", "qos": 0, "retain": False, "payload": {"raw": "not json"}},
    ]
