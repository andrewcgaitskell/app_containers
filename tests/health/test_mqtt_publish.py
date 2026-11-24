"""Unit tests for health/mqtt-publish.py with paho-mqtt replaced by a fake."""
import importlib.util
import sys
import types
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "health" / "mqtt-publish.py"


@pytest.fixture
def mqtt(monkeypatch):
    calls = []
    fake_publish = types.ModuleType("paho.mqtt.publish")
    fake_publish.error = None

    def single(**kwargs):
        if fake_publish.error:
            raise fake_publish.error
        calls.append(kwargs)

    fake_publish.single = single
    paho = types.ModuleType("paho")
    paho_mqtt = types.ModuleType("paho.mqtt")
    paho.mqtt, paho_mqtt.publish = paho_mqtt, fake_publish
    monkeypatch.setitem(sys.modules, "paho", paho)
    monkeypatch.setitem(sys.modules, "paho.mqtt", paho_mqtt)
    monkeypatch.setitem(sys.modules, "paho.mqtt.publish", fake_publish)

    spec = importlib.util.spec_from_file_location("mqtt_publish", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def run(*args):
        monkeypatch.setattr(sys, "argv", ["mqtt_publish.py", *args])
        return module.main()

    run.calls = calls
    run.fake = fake_publish
    return run


def test_defaults(mqtt):
    assert mqtt("--topic", "t/1", "--payload", '{"a": 1}') == 0
    assert mqtt.calls == [{
        "topic": "t/1", "payload": '{"a": 1}', "qos": 0, "retain": False,
        "hostname": "localhost", "port": 1883, "auth": None,
    }]


def test_all_options(mqtt):
    mqtt("--host", "broker", "--port", "1884", "--topic", "t", "--payload", "p",
         "--qos", "1", "--retain", "--username", "user", "--password", "placeholder")

    call = mqtt.calls[0]
    assert (call["hostname"], call["port"], call["qos"], call["retain"]) == ("broker", 1884, 1, True)
    assert call["auth"] == {"username": "user", "password": "placeholder"}


def test_username_without_password_sends_empty_password(mqtt):
    mqtt("--topic", "t", "--payload", "p", "--username", "user")

    assert mqtt.calls[0]["auth"] == {"username": "user", "password": ""}


def test_publish_failure_returns_1(mqtt, capsys):
    mqtt.fake.error = ConnectionRefusedError("refused")

    assert mqtt("--topic", "t", "--payload", "p") == 1
    assert "MQTT publish failed: refused" in capsys.readouterr().err


@pytest.mark.parametrize("args", [["--payload", "p"], ["--topic", "t"], ["--topic", "t", "--payload", "p", "--qos", "3"]])
def test_bad_arguments_exit_2(mqtt, args):
    with pytest.raises(SystemExit) as exc:
        mqtt(*args)
    assert exc.value.code == 2
    assert mqtt.calls == []
