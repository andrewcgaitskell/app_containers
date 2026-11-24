"""Behaviour tests for the health container's cron scripts.

Each test copies the scripts into a temporary directory (laid out like
/scripts in the image) and runs them with bash. Every external command
they use - curl, docker, ping, speedtest-cli and the MQTT publisher - is
replaced by a stub that records its arguments, so nothing real is
contacted, restarted, or published.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

HEALTH = Path(__file__).resolve().parents[2] / "health"
SYSTEM_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

RECORD = 'printf "%s\\n" "$*" >> "$CALLS/{name}"\n'

# Fake venv python: real python for the inline JSON parser ("python3 - ..."),
# otherwise it stands in for mqtt_publish.py and records the call.
FAKE_VENV_PYTHON = f"""#!/bin/bash
if [ "$1" = "-" ]; then exec "{sys.executable}" "$@"; fi
exec "{sys.executable}" -c 'import json, os, sys; open(os.path.join(os.environ["CALLS"], "mqtt.jsonl"), "a").write(json.dumps(sys.argv[1:]) + "\\n")' "$@"
"""

FAKE_SPEEDTEST = """#!/bin/bash
printf '%s' "${SPEEDTEST_JSON:-}"
[ -n "${SPEEDTEST_STDERR:-}" ] && printf '%s' "$SPEEDTEST_STDERR" >&2
exit "${SPEEDTEST_EXIT:-0}"
"""


class Sandbox:
    def __init__(self, root: Path):
        self.root = root
        self.bin = root / "bin"
        self.calls = root / "calls"
        self.scripts = root / "scripts"
        self.venv = root / "venv"
        self.state = root / "state"
        self.log = root / "log" / "script.log"
        for d in (self.bin, self.calls, self.scripts, self.venv / "bin", self.state):
            d.mkdir(parents=True)

        # Same layout as the image: scripts plus helper renamed to mqtt_publish.py
        for script in HEALTH.glob("*.sh"):
            shutil.copy(script, self.scripts / script.name)
        shutil.copy(HEALTH / "mqtt-publish.py", self.scripts / "mqtt_publish.py")

        self._write(self.venv / "bin" / "python3", FAKE_VENV_PYTHON)
        self._write(self.venv / "bin" / "speedtest-cli", FAKE_SPEEDTEST)

        # Always stub anything that could touch the network or the host.
        for name in ("curl", "docker", "ping"):
            self.stub(name, "exit 0")

    @staticmethod
    def _write(path: Path, text: str):
        path.write_text(text)
        path.chmod(0o755)

    def stub(self, name: str, body: str):
        self._write(self.bin / name, "#!/bin/bash\n" + RECORD.format(name=name) + body + "\n")

    def calls_to(self, name: str) -> list[str]:
        f = self.calls / name
        return f.read_text().splitlines() if f.exists() else []

    def mqtt_messages(self) -> list[dict]:
        f = self.calls / "mqtt.jsonl"
        messages = []
        for line in (f.read_text().splitlines() if f.exists() else []):
            argv = json.loads(line)
            messages.append({
                "topic": argv[argv.index("--topic") + 1],
                "raw": argv[argv.index("--payload") + 1],
                "retain": "--retain" in argv,
                "host": argv[argv.index("--host") + 1],
            })
        return messages

    def log_text(self) -> str:
        return self.log.read_text() if self.log.exists() else ""

    def run(self, script: str, **env) -> subprocess.CompletedProcess:
        full_env = {
            "PATH": f"{self.bin}:{SYSTEM_PATH}",
            "HOME": str(self.root),
            "TZ": "UTC",
            "CALLS": str(self.calls),
            "LOGFILE": str(self.log),
            "STATE_DIR": str(self.state),
            "STATE_FILE": str(self.state / "net-last-state"),
            "VENV_DIR": str(self.venv),
            **{k: str(v) for k, v in env.items()},
        }
        return subprocess.run(
            ["bash", str(self.scripts / script)],
            env=full_env, capture_output=True, text=True, timeout=60,
        )


@pytest.fixture
def sb(tmp_path):
    return Sandbox(tmp_path)


def payload(msg):
    return json.loads(msg["raw"])


# ------------------------------------------------------- ha-health-monitor.sh

HA = "ha-health-monitor.sh"


def fail_count(sb):
    return (sb.state / "ha_fail_count").read_text().strip()


def test_ha_healthy_resets_count_and_does_not_restart(sb):
    result = sb.run(HA)

    assert result.returncode == 0
    assert sb.calls_to("curl")[0].endswith("http://localhost:8123/manifest.json")
    assert fail_count(sb) == "0"
    assert "Home Assistant is responding normally" in sb.log_text()
    assert sb.calls_to("docker") == []


def test_ha_first_failure_counts_but_does_not_restart(sb):
    sb.stub("curl", "exit 7")

    sb.run(HA)

    assert fail_count(sb) == "1"
    assert "Health check failed (1/3)" in sb.log_text()
    assert sb.calls_to("docker") == []


def test_ha_third_failure_restarts_and_starts_cooldown(sb):
    sb.stub("curl", "exit 7")
    (sb.state / "ha_fail_count").write_text("2\n")

    before = int(time.time())
    sb.run(HA)

    assert sb.calls_to("docker") == ["restart homeassistant"]
    assert fail_count(sb) == "0"
    cooldown_until = int((sb.state / "ha_restart_cooldown_until").read_text())
    assert before + 85 <= cooldown_until <= int(time.time()) + 90
    assert "restarting container 'homeassistant'" in sb.log_text()


def test_ha_skips_check_during_cooldown(sb):
    (sb.state / "ha_restart_cooldown_until").write_text(str(int(time.time()) + 60))

    result = sb.run(HA)

    assert result.returncode == 0
    assert sb.calls_to("curl") == []
    assert "Skipping check" in sb.log_text()


def test_ha_expired_cooldown_is_cleared_and_check_runs(sb):
    cooldown = sb.state / "ha_restart_cooldown_until"
    cooldown.write_text(str(int(time.time()) - 1))

    sb.run(HA)

    assert not cooldown.exists()
    assert len(sb.calls_to("curl")) == 1


def test_ha_recovery_after_failures_is_logged(sb):
    (sb.state / "ha_fail_count").write_text("2\n")

    sb.run(HA)

    assert fail_count(sb) == "0"
    assert "responding normally again" in sb.log_text()


def test_ha_corrupt_fail_count_treated_as_zero(sb):
    sb.stub("curl", "exit 7")
    (sb.state / "ha_fail_count").write_text("garbage\n")

    sb.run(HA)

    assert fail_count(sb) == "1"


def test_ha_trims_oversized_log(sb):
    sb.log.parent.mkdir(parents=True)
    sb.log.write_text("".join(f"old line {i}\n" for i in range(3000)))

    sb.run(HA, MAX_LOG_SIZE=100)

    lines = sb.log_text().splitlines()
    assert len(lines) <= 2502
    assert "old line 0" not in lines
    assert lines[-1].endswith("Log trimmed successfully")


# ---------------------------------------------------------- pg-dump-trigger.sh

PG = "pg-dump-trigger.sh"
CURL_WRITEOUT = 'printf "%s\\nHTTP_STATUS:%s" "$CURL_BODY" "$CURL_STATUS"; exit "${CURL_EXIT:-0}"'


def test_pg_dump_trigger_success(sb):
    sb.stub("curl", CURL_WRITEOUT)

    result = sb.run(PG, CURL_BODY='{"ok": true}', CURL_STATUS=200)

    assert result.returncode == 0
    call = sb.calls_to("curl")[0]
    assert "-X POST" in call
    assert call.endswith("http://localhost:8090/trigger_data_dump")
    assert 'succeeded (HTTP 200). Response: {"ok": true}' in sb.log_text()


@pytest.mark.parametrize("status, exit_code", [(500, 0), ("000", 7)])
def test_pg_dump_trigger_failure_is_logged(sb, status, exit_code):
    sb.stub("curl", CURL_WRITEOUT)

    sb.run(PG, CURL_BODY="error", CURL_STATUS=status, CURL_EXIT=exit_code)

    assert f"WARNING: Data dump trigger returned HTTP {status}" in sb.log_text()


# ---------------------------------------------------- net-connectivity-check.sh

NET = "net-connectivity-check.sh"
PING_STUB = 'last="${@: -1}"; for h in ${PING_FAIL:-}; do [ "$h" = "$last" ] && exit 1; done; exit 0'


def last_state(sb):
    return (sb.state / "net-last-state").read_text().strip()


def test_net_all_up_publishes_retained_state_only(sb):
    sb.stub("ping", PING_STUB)

    result = sb.run(NET)

    assert result.returncode == 0
    assert sb.calls_to("ping") == [f"-c 2 -W 3 {h}" for h in ("1.1.1.1", "8.8.8.8", "9.9.9.9")]
    [msg] = sb.mqtt_messages()
    assert msg["topic"] == "net/connectivity/state"
    assert msg["retain"] is True
    assert msg["host"] == "localhost"
    assert payload(msg) | {"timestamp": None} == {
        "state": "up", "hosts_up": 3, "hosts_total": 3, "timestamp": None,
    }
    assert last_state(sb) == "up"
    assert "Connectivity OK (3/3" in result.stdout


def test_net_partial_failure_is_still_up(sb):
    sb.stub("ping", PING_STUB)

    sb.run(NET, PING_FAIL="1.1.1.1 8.8.8.8")

    [msg] = sb.mqtt_messages()
    assert payload(msg)["state"] == "up"
    assert payload(msg)["hosts_up"] == 1


def test_net_all_down_publishes_anomaly(sb):
    sb.stub("ping", PING_STUB)

    result = sb.run(NET, PING_FAIL="1.1.1.1 8.8.8.8 9.9.9.9")

    state, anomaly = sb.mqtt_messages()
    assert payload(state)["state"] == "down"
    assert anomaly["topic"] == "net/connectivity/anomaly"
    assert anomaly["retain"] is False
    assert payload(anomaly)["type"] == "connectivity_down"
    assert payload(anomaly)["failed_hosts"] == "1.1.1.1 8.8.8.8 9.9.9.9"
    assert last_state(sb) == "down"
    assert "Connectivity DOWN" in result.stdout


def test_net_restored_after_down_publishes_anomaly(sb):
    sb.stub("ping", PING_STUB)
    (sb.state / "net-last-state").write_text("down\n")

    sb.run(NET)

    state, anomaly = sb.mqtt_messages()
    assert payload(state)["state"] == "up"
    assert payload(anomaly)["type"] == "connectivity_restored"
    assert last_state(sb) == "up"


def test_net_missing_venv_fails_without_publishing(sb):
    result = sb.run(NET, VENV_DIR=sb.root / "no-venv")

    assert result.returncode == 1
    assert "venv not found" in result.stderr
    assert sb.calls_to("ping") == []


def test_net_missing_publisher_fails(sb):
    (sb.scripts / "mqtt_publish.py").unlink()

    result = sb.run(NET)

    assert result.returncode == 1
    assert "mqtt_publish.py not found" in result.stderr


# ------------------------------------------------------- net-speedtest-daily.sh

SPEED = "net-speedtest-daily.sh"


def speedtest_json(download, upload, ping, name="London", sponsor="Example ISP"):
    return json.dumps({
        "download": download, "upload": upload, "ping": ping,
        "server": {"name": name, "sponsor": sponsor},
    })


def test_speedtest_good_result_publishes_retained_reading(sb):
    result = sb.run(SPEED, SPEEDTEST_JSON=speedtest_json(93_400_000, 20_000_000, 12.34))

    assert result.returncode == 0
    [msg] = sb.mqtt_messages()
    assert msg["topic"] == "net/speedtest/result"
    assert msg["retain"] is True
    assert payload(msg) | {"timestamp": None} == {
        "timestamp": None, "download_mbps": 93.4, "upload_mbps": 20.0,
        "ping_ms": 12.3, "server": "London", "sponsor": "Example ISP",
    }
    assert "No anomalies detected." in result.stdout


def test_speedtest_slow_result_publishes_anomaly(sb):
    sb.run(SPEED, SPEEDTEST_JSON=speedtest_json(10_000_000, 5_000_000, 120))

    reading, anomaly = sb.mqtt_messages()
    assert anomaly["topic"] == "net/speedtest/anomaly"
    body = payload(anomaly)
    assert body["type"] == "speedtest_anomaly"
    assert "download 10.0Mbps below minimum 50Mbps" in body["reasons"]
    assert "upload 5.0Mbps below minimum 10Mbps" in body["reasons"]
    assert "ping 120.0ms above maximum 80ms" in body["reasons"]


def test_speedtest_failure_publishes_failed_anomaly(sb):
    result = sb.run(SPEED, SPEEDTEST_EXIT=1, SPEEDTEST_STDERR="Cannot retrieve speedtest configuration")

    assert result.returncode == 1
    [msg] = sb.mqtt_messages()
    assert msg["topic"] == "net/speedtest/anomaly"
    assert payload(msg)["type"] == "speedtest_failed"
    assert "Cannot retrieve speedtest configuration" in payload(msg)["error"]


@pytest.mark.parametrize(
    "stderr, expected",
    [
        ('Unable to connect to "www.speedtest.net"', 'Unable to connect to "www.speedtest.net"'),
        ("path C:\\temp\\x failed", "path C:\\temp\\x failed"),
        ("tab\there\rcr", "tab here cr"),
    ],
)
def test_speedtest_failure_error_text_is_escaped(sb, stderr, expected):
    sb.run(SPEED, SPEEDTEST_EXIT=1, SPEEDTEST_STDERR=stderr)

    [msg] = sb.mqtt_messages()
    assert payload(msg)["type"] == "speedtest_failed"
    assert payload(msg)["error"] == expected


def test_speedtest_server_names_are_escaped(sb):
    sb.run(SPEED, SPEEDTEST_JSON=speedtest_json(
        93_400_000, 20_000_000, 12, name='St "Albans"', sponsor="Back\\slash ISP"))

    [msg] = sb.mqtt_messages()
    assert payload(msg)["server"] == 'St "Albans"'
    assert payload(msg)["sponsor"] == "Back\\slash ISP"


def test_speedtest_missing_venv_fails(sb):
    result = sb.run(SPEED, VENV_DIR=sb.root / "no-venv")

    assert result.returncode == 1
    assert "venv not found" in result.stderr
    assert sb.mqtt_messages() == []
