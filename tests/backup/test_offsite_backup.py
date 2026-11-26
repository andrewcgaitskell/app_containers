"""Behaviour tests for backup/offsite-backup.sh.

The script runs against a fake /opt/data tree in a temp directory. gpg and
rclone are stubs: gpg passes data through unencrypted (so the archive can
be inspected) and rclone "uploads" into a local folder standing in for
Google Drive. Nothing real is encrypted, uploaded or deleted.
"""
import os
import subprocess
import tarfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "backup" / "offsite-backup.sh"
SYSTEM_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

RECORD = 'printf "%s\\n" "$*" >> "$CALLS/{name}"\n'

FAKE_GPG = """
out=""
while [ $# -gt 0 ]; do
    case "$1" in --output) out=$2; shift ;; esac
    shift
done
cat > "$out"
exit "${GPG_EXIT:-0}"
"""

FAKE_RCLONE = """
cmd=$1; shift
case "$cmd" in
    copy)
        [ "${RCLONE_COPY_EXIT:-0}" -eq 0 ] || exit "$RCLONE_COPY_EXIT"
        dest="$FAKE_DRIVE/${2#*:}"; mkdir -p "$dest"; cp "$1" "$dest/" ;;
    lsf)
        remote="${@: -1}"; ls -1 "$FAKE_DRIVE/${remote#*:}" 2>/dev/null ;;
    deletefile)
        rm "$FAKE_DRIVE/${1#*:}" ;;
esac
"""


class Sandbox:
    def __init__(self, root: Path):
        self.root = root
        self.data = root / "opt_data"
        self.bin = root / "bin"
        self.calls = root / "calls"
        self.drive = root / "drive"
        self.work = root / "work"
        self.passphrase = root / "passphrase"
        for d in (self.data, self.bin, self.calls, self.drive):
            d.mkdir()
        self.passphrase.write_text("test-passphrase\n")
        self.stub("gpg", FAKE_GPG)
        self.stub("rclone", FAKE_RCLONE)

    def stub(self, name: str, body: str):
        path = self.bin / name
        path.write_text("#!/bin/bash\n" + RECORD.format(name=name) + body)
        path.chmod(0o755)

    def file(self, rel: str, text: str = "x"):
        path = self.data / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def populate(self):
        self.file("home_assistant/config/configuration.yaml")
        self.file("home_assistant/config/.storage/core.entity_registry")
        self.file("home_assistant/config/home-assistant_v2.db")
        self.file("home_assistant/config/home-assistant.log")
        self.file("home_assistant/config/backups/ha.tar")
        self.file("zigbee2mqtt_data/configuration.yaml")
        self.file("zigbee2mqtt_data/coordinator_backup.json")
        self.file("zigbee2mqtt_data/log/2026-11-26/log.log")
        self.file("otbr/data/thread.dat")
        self.file("matter/data/fabric.json")
        self.file("esphome/config/device.yaml")
        self.file("esphome/config/.esphome/build/big.bin")
        self.file("app_containers/compose/.env", "POSTGRES_PASSWORD=changeme\n")
        self.file("app_containers/quart_app/app.py")
        self.file("blockly/programs/prog.xml")
        self.file("jupyter/notebook.ipynb")
        self.file("mosquitto/data/mosquitto.db")
        self.file("postgres_data/data/PG_VERSION")
        self.file("postgres_data/backups/data_dump_20261124_0601.zip")
        self.file("postgres_data/backups/data_dump_20261125_0601.zip")
        self.file("postgres_data/backups/data_dump_20261125_0601.sql")
        self.file("postgres_data/backups/data_data_only_20261125_0601.zip")

    def run(self, **env):
        full_env = {
            "PATH": f"{self.bin}:{SYSTEM_PATH}",
            "HOME": str(self.root),
            "CALLS": str(self.calls),
            "FAKE_DRIVE": str(self.drive),
            "DATA_ROOT": str(self.data),
            "PASSPHRASE_FILE": str(self.passphrase),
            "WORK_DIR": str(self.work),
            "RCLONE_REMOTE": "gdrive:pi-backups",
        }
        full_env.update({k: str(v) for k, v in env.items()})
        return subprocess.run(["bash", str(SCRIPT)], env=full_env,
                              capture_output=True, text=True, timeout=60)

    def uploaded(self) -> list[str]:
        folder = self.drive / "pi-backups"
        return sorted(p.name for p in folder.iterdir()) if folder.exists() else []

    def archive_members(self) -> set[str]:
        (name,) = [n for n in self.uploaded() if n.startswith("home-backup-")][-1:]
        with tarfile.open(self.drive / "pi-backups" / name, "r:gz") as tar:
            return {m.name for m in tar.getmembers() if m.isfile()}

    def calls_to(self, name: str) -> list[str]:
        path = self.calls / name
        return path.read_text().splitlines() if path.exists() else []


@pytest.fixture
def sb(tmp_path):
    return Sandbox(tmp_path)


def test_script_syntax():
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)


def test_backs_up_critical_data_and_skips_noise(sb):
    sb.populate()
    result = sb.run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Done: home-backup-" in result.stdout

    members = sb.archive_members()
    for wanted in (
        "home_assistant/config/configuration.yaml",
        "home_assistant/config/.storage/core.entity_registry",
        "zigbee2mqtt_data/coordinator_backup.json",
        "otbr/data/thread.dat",
        "matter/data/fabric.json",
        "esphome/config/device.yaml",
        "app_containers/compose/.env",
        "blockly/programs/prog.xml",
        "jupyter/notebook.ipynb",
        "postgres_data/backups/data_dump_20261125_0601.zip",
    ):
        assert wanted in members, wanted

    for unwanted in (
        "home_assistant/config/home-assistant_v2.db",
        "home_assistant/config/home-assistant.log",
        "home_assistant/config/backups/ha.tar",
        "zigbee2mqtt_data/log/2026-11-26/log.log",
        "esphome/config/.esphome/build/big.bin",
        "app_containers/quart_app/app.py",
        "mosquitto/data/mosquitto.db",
        "postgres_data/data/PG_VERSION",
        "postgres_data/backups/data_dump_20261124_0601.zip",
        "postgres_data/backups/data_dump_20261125_0601.sql",
        "postgres_data/backups/data_data_only_20261125_0601.zip",
    ):
        assert unwanted not in members, unwanted


def test_encrypts_with_passphrase_file(sb):
    sb.populate()
    assert sb.run().returncode == 0
    (call,) = sb.calls_to("gpg")
    assert "--symmetric" in call
    assert "--cipher-algo AES256" in call
    assert f"--passphrase-file {sb.passphrase}" in call


def test_local_archive_removed_after_upload(sb):
    sb.populate()
    assert sb.run().returncode == 0
    assert list(sb.work.iterdir()) == []


def test_falls_back_to_sql_dump_when_no_zip(sb):
    sb.file("home_assistant/config/configuration.yaml")
    sb.file("postgres_data/backups/data_dump_20261125_0601.sql")
    assert sb.run().returncode == 0
    assert "postgres_data/backups/data_dump_20261125_0601.sql" in sb.archive_members()


def test_missing_folders_warn_but_continue(sb):
    sb.file("home_assistant/config/configuration.yaml")
    result = sb.run()
    assert result.returncode == 0
    assert "zigbee2mqtt_data not found" in result.stdout
    assert "no Postgres dump found" in result.stdout
    assert len(sb.uploaded()) == 1


def test_fails_when_nothing_to_back_up(sb):
    result = sb.run()
    assert result.returncode != 0
    assert "nothing to back up" in result.stdout
    assert sb.uploaded() == []


def test_fails_without_passphrase(sb):
    sb.populate()
    sb.passphrase.write_text("")
    result = sb.run()
    assert result.returncode != 0
    assert "passphrase file" in result.stdout
    assert sb.calls_to("rclone") == []


def test_rejects_bad_keep(sb):
    sb.populate()
    result = sb.run(KEEP="0")
    assert result.returncode != 0
    assert sb.calls_to("rclone") == []


def test_gpg_failure_stops_before_upload(sb):
    sb.populate()
    result = sb.run(GPG_EXIT=2)
    assert result.returncode != 0
    assert "encryption failed" in result.stdout
    assert sb.calls_to("rclone") == []


def test_upload_failure_skips_pruning(sb):
    sb.populate()
    folder = sb.drive / "pi-backups"
    folder.mkdir()
    for day in range(1, 6):
        (folder / f"home-backup-202611{day:02d}_0630.tar.gz.gpg").write_text("old")
    result = sb.run(RCLONE_COPY_EXIT=1, KEEP=2)
    assert result.returncode != 0
    assert "upload failed" in result.stdout
    assert len(sb.uploaded()) == 5
    assert list(sb.work.iterdir()) == []


def test_prunes_to_keep_newest_and_leaves_other_files(sb):
    sb.populate()
    folder = sb.drive / "pi-backups"
    folder.mkdir()
    for day in range(1, 6):
        (folder / f"home-backup-202611{day:02d}_0630.tar.gz.gpg").write_text("old")
    (folder / "notes.txt").write_text("keep me")
    (folder / "home-backup-manual.tar.gz.gpg").write_text("keep me")

    result = sb.run(KEEP=3)
    assert result.returncode == 0, result.stdout + result.stderr

    remaining = sb.uploaded()
    backups = [n for n in remaining if n[len("home-backup-"):][:1].isdigit()]
    assert len(backups) == 3
    assert "home-backup-20261104_0630.tar.gz.gpg" in backups
    assert "home-backup-20261105_0630.tar.gz.gpg" in backups
    assert "notes.txt" in remaining
    assert "home-backup-manual.tar.gz.gpg" in remaining
