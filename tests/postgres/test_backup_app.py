"""Tests for the Postgres container's backup app (postgres/quart/).

pg_dump and zip are never executed: subprocess.run is replaced by a fake
that records each command.
"""
import importlib.util
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

PG_QUART = Path(__file__).resolve().parents[2] / "postgres" / "quart"
FIXED_NOW = datetime(2026, 11, 24, 6, 1, 30)


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, PG_QUART / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def pg(monkeypatch, tmp_path):
    monkeypatch.setenv("POSTGRES_USER", "placeholder_user")
    module = load("pg_backup_app", "app.py")
    module.BACKUP_DIR = str(tmp_path / "backups")

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return FIXED_NOW

    monkeypatch.setattr(module, "datetime", FixedDatetime)

    module.commands = []
    module.fail_on = {}

    def fake_run(cmd, **kwargs):
        module.commands.append((cmd, kwargs))
        error = module.fail_on.get(cmd[0])
        if error:
            raise error
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    return module


@pytest.fixture
def client(pg):
    pg.app.config["TESTING"] = True
    return pg.app.test_client()


# ------------------------------------------------------------------- routes

@pytest.mark.parametrize(
    "route, prefix, extra_args",
    [
        ("/trigger_data_dump", "data_dump", []),
        ("/trigger_data_data_only", "data_data_only", ["--data-only"]),
    ],
)
async def test_dump_runs_pg_dump_then_zip(pg, client, route, prefix, extra_args):
    backups = Path(pg.BACKUP_DIR)
    sql = f"{backups}/{prefix}_20261124_0601.sql"
    zipped = f"{backups}/{prefix}_20261124_0601.zip"

    resp = await client.post(route)

    assert resp.status_code == 200
    assert await resp.get_json() == {"message": f"Data backup successful: {sql}", "deleted": []}
    assert backups.is_dir()

    (dump_cmd, dump_kwargs), (zip_cmd, zip_kwargs) = pg.commands
    assert dump_cmd == ["pg_dump", *extra_args, "-U", "placeholder_user", "-d", "data", "-f", sql]
    assert dump_kwargs["check"] is True
    assert zip_cmd == ["zip", "-j", zipped, sql]
    assert zip_kwargs["check"] is True


@pytest.mark.parametrize("route", ["/trigger_data_dump", "/trigger_data_data_only"])
async def test_missing_postgres_user_returns_500_without_running_pg_dump(pg, client, monkeypatch, route):
    monkeypatch.delenv("POSTGRES_USER")

    resp = await client.post(route)

    assert resp.status_code == 500
    assert (await resp.get_json())["error"] == "POSTGRES_USER environment variable is not set"
    assert pg.commands == []


def test_no_hard_coded_database_users():
    source = (PG_QUART / "app.py").read_text()
    assert "pi5ha" not in source
    assert "pythonuser" not in source


@pytest.mark.parametrize("route", ["/trigger_data_dump", "/trigger_data_data_only"])
async def test_pg_dump_failure_returns_500_and_skips_zip(pg, client, route):
    pg.fail_on["pg_dump"] = subprocess.CalledProcessError(1, "pg_dump")

    resp = await client.post(route)

    assert resp.status_code == 500
    assert "pg_dump" in (await resp.get_json())["error"]
    assert [cmd[0] for cmd, _ in pg.commands] == ["pg_dump"]


async def test_missing_zip_binary_returns_500(pg, client):
    pg.fail_on["zip"] = FileNotFoundError("zip")

    resp = await client.post("/trigger_data_dump")

    assert resp.status_code == 500
    assert [cmd[0] for cmd, _ in pg.commands] == ["pg_dump", "zip"]


@pytest.mark.parametrize("route", ["/trigger_data_dump", "/trigger_data_data_only"])
async def test_get_is_not_allowed(pg, client, route):
    resp = await client.get(route)

    assert resp.status_code == 405
    assert pg.commands == []


def test_backup_dir_defaults_to_backups(monkeypatch):
    monkeypatch.delenv("BACKUP_DIR", raising=False)

    assert load("pg_backup_app_defaults", "app.py").BACKUP_DIR == "/backups"


# ------------------------------------------------------------------ cleanup

def make_files(directory, *names):
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        (directory / name).write_text("x")


def remaining(directory):
    return sorted(p.name for p in directory.iterdir())


def test_cleanup_deletes_only_old_dump_files(pg):
    backups = Path(pg.BACKUP_DIR)
    make_files(
        backups,
        # older than 30 days -> deleted (both types, both extensions)
        "data_dump_20261001_0601.sql", "data_dump_20261001_0601.zip",
        "data_data_only_20261001_0601.sql", "data_data_only_20261001_0601.zip",
        # within 30 days -> kept
        "data_dump_20261030_0601.sql", "data_dump_20261030_0601.zip",
        "data_data_only_20261124_0601.zip",
        # not files this app creates -> never touched, however old they look
        "last_backup_timestamp.txt", "data_dump_20200101_0000.sql.bak",
        "manual_20200101_0000.sql", "data_dump_old.zip", "notes.txt",
    )

    deleted = pg.cleanup_old_backups()

    assert deleted == [
        "data_data_only_20261001_0601.sql", "data_data_only_20261001_0601.zip",
        "data_dump_20261001_0601.sql", "data_dump_20261001_0601.zip",
    ]
    assert remaining(backups) == sorted([
        "data_dump_20261030_0601.sql", "data_dump_20261030_0601.zip",
        "data_data_only_20261124_0601.zip",
        "last_backup_timestamp.txt", "data_dump_20200101_0000.sql.bak",
        "manual_20200101_0000.sql", "data_dump_old.zip", "notes.txt",
    ])


def test_cleanup_boundary_is_exactly_keep_days(pg):
    backups = Path(pg.BACKUP_DIR)
    # FIXED_NOW is 2026-11-24 06:01:30, so the cutoff is 2026-10-25 06:01:30.
    make_files(backups, "data_dump_20261025_0601.zip", "data_dump_20261025_0602.zip",
               "data_dump_20261124_0601.zip")

    assert pg.cleanup_old_backups() == ["data_dump_20261025_0601.zip"]


def test_cleanup_always_keeps_newest_of_each_type(pg):
    backups = Path(pg.BACKUP_DIR)
    make_files(
        backups,
        "data_dump_20250101_0601.sql", "data_dump_20250101_0601.zip",
        "data_dump_20250102_0601.sql", "data_dump_20250102_0601.zip",
        "data_data_only_20250101_0601.zip",
    )

    pg.cleanup_old_backups()

    assert remaining(backups) == [
        "data_data_only_20250101_0601.zip",
        "data_dump_20250102_0601.sql", "data_dump_20250102_0601.zip",
    ]


def test_cleanup_uses_keep_days_setting(pg):
    backups = Path(pg.BACKUP_DIR)
    make_files(backups, "data_dump_20261115_0601.zip", "data_dump_20261124_0601.zip")
    pg.BACKUP_KEEP_DAYS = 7

    assert pg.cleanup_old_backups() == ["data_dump_20261115_0601.zip"]


def test_cleanup_missing_dir_returns_empty(pg):
    assert pg.cleanup_old_backups() == []


def test_cleanup_delete_error_is_logged_not_raised(pg, monkeypatch, caplog):
    backups = Path(pg.BACKUP_DIR)
    make_files(backups, "data_dump_20261001_0601.zip", "data_dump_20261124_0601.zip")

    def refuse(path):
        raise PermissionError("read-only")

    monkeypatch.setattr(pg.os, "remove", refuse)

    assert pg.cleanup_old_backups() == []
    assert "could not delete data_dump_20261001_0601.zip" in caplog.text


@pytest.mark.parametrize("route", ["/trigger_data_dump", "/trigger_data_data_only"])
async def test_backup_route_runs_cleanup(pg, client, route):
    backups = Path(pg.BACKUP_DIR)
    make_files(backups, "data_dump_20261001_0601.zip", "data_data_only_20261001_0601.zip",
               "data_dump_20261120_0601.zip", "data_data_only_20261120_0601.zip")

    resp = await client.post(route)

    assert resp.status_code == 200
    assert (await resp.get_json())["deleted"] == [
        "data_data_only_20261001_0601.zip", "data_dump_20261001_0601.zip",
    ]


async def test_backup_not_cleaned_up_when_dump_fails(pg, client):
    backups = Path(pg.BACKUP_DIR)
    make_files(backups, "data_dump_20261001_0601.zip", "data_dump_20261120_0601.zip")
    pg.fail_on["pg_dump"] = subprocess.CalledProcessError(1, "pg_dump")

    resp = await client.post("/trigger_data_dump")

    assert resp.status_code == 500
    assert "data_dump_20261001_0601.zip" in remaining(backups)


@pytest.mark.parametrize("value, expected", [(None, 30), ("7", 7), ("abc", 30), ("0", 30), ("-5", 30)])
def test_keep_days_setting(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("BACKUP_KEEP_DAYS", raising=False)
    else:
        monkeypatch.setenv("BACKUP_KEEP_DAYS", value)

    assert load("pg_backup_app_keep_days", "app.py").BACKUP_KEEP_DAYS == expected


# --------------------------------------------------------- timestamp helpers

def test_last_backup_defaults_to_epoch(pg):
    assert pg.get_last_backup_timestamp() == datetime(1970, 1, 1, tzinfo=timezone.utc)


def test_last_backup_round_trip(pg):
    Path(pg.BACKUP_DIR).mkdir()
    pg.update_last_backup_timestamp("2026-11-24T06:01:00+00:00")

    assert pg.get_last_backup_timestamp() == datetime(2026, 11, 24, 6, 1, tzinfo=timezone.utc)


def test_last_backup_invalid_file_raises(pg):
    Path(pg.BACKUP_DIR).mkdir()
    pg.update_last_backup_timestamp("not a date")

    with pytest.raises(ValueError, match="Invalid timestamp format"):
        pg.get_last_backup_timestamp()


# ------------------------------------------------------- no database pool

def test_app_has_no_startup_or_shutdown_hooks(pg):
    # The app only shells out to pg_dump; it should not open DB connections.
    assert pg.app.before_serving_funcs == []
    assert pg.app.after_serving_funcs == []


def test_app_does_not_import_asyncpg():
    source = (PG_QUART / "app.py").read_text()
    assert "asyncpg" not in source
    assert not (PG_QUART / "db.py").exists()
