"""Static checks that the health image, crontab and scripts fit together."""
import re
import subprocess
from pathlib import Path

import pytest

HEALTH = Path(__file__).resolve().parents[2] / "health"
DOCKERFILE = (HEALTH / "Dockerfile").read_text()
CRONTAB = (HEALTH / "health-crontab").read_text()

COPIES = dict(re.findall(r"^COPY\s+(\S+)\s+(\S+)\s*$", DOCKERFILE, re.MULTILINE))


def active_cron_lines():
    return [line for line in CRONTAB.splitlines() if line.strip() and not line.lstrip().startswith("#")]


@pytest.mark.parametrize("script", sorted(p.name for p in HEALTH.glob("*.sh")))
def test_shell_syntax(script):
    result = subprocess.run(["bash", "-n", str(HEALTH / script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_dockerfile_copy_sources_exist():
    missing = [src for src in COPIES if not (HEALTH / src).exists()]
    assert missing == []


def test_mqtt_helper_installed_under_name_scripts_expect():
    # The shell scripts look for mqtt_publish.py next to themselves.
    assert COPIES.get("mqtt-publish.py") == "/scripts/mqtt_publish.py"


def test_crontab_ends_with_newline():
    assert CRONTAB.endswith("\n")


def test_crontab_entries_are_well_formed_and_point_at_installed_scripts():
    installed = set(COPIES.values())
    lines = active_cron_lines()
    assert lines, "crontab has no active entries"
    for line in lines:
        fields = line.split(None, 6)
        assert len(fields) == 7, line
        assert fields[5] == "root", line
        script = fields[6].split()[0]
        assert script in installed, f"{script} is not copied into the image"
