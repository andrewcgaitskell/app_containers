"""Tests for the Postgres container's backup app (postgres/quart/).

pg_dump and zip are never executed: subprocess.run is replaced by a fake
that records each command. The asyncpg pool is faked too, and only
placeholder credentials are used.
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


class FakePool:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


@pytest.fixture
def db(monkeypatch):
    module = load("pg_backup_db", "db.py")
    # app.py does `from db import ...`
    monkeypatch.setitem(sys.modules, "db", module)
    return module


@pytest.fixture
def pg(db, monkeypatch, tmp_path):
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
    # test_client() does not run before_serving, so no DB pool is created.
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
    assert await resp.get_json() == {"message": f"Data backup successful: {sql}"}
    assert backups.is_dir()

    (dump_cmd, dump_kwargs), (zip_cmd, zip_kwargs) = pg.commands
    assert dump_cmd == ["pg_dump", *extra_args, "-U", "pi5ha", "-d", "data", "-f", sql]
    assert dump_kwargs["check"] is True
    assert dump_kwargs["env"]["PGUSER"] == "pythonuser"
    assert zip_cmd == ["zip", "-j", zipped, sql]
    assert zip_kwargs["check"] is True


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


def test_backup_dir_defaults_to_backups(db, monkeypatch):
    monkeypatch.delenv("BACKUP_DIR", raising=False)

    assert load("pg_backup_app_defaults", "app.py").BACKUP_DIR == "/backups"


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


# ------------------------------------------------------------------ db pool

@pytest.fixture
def pg_env(monkeypatch):
    for key, value in {
        "POSTGRES_USER": "placeholder_user",
        "POSTGRES_PASSWORD": "placeholder_password",
        "POSTGRES_DB": "placeholder_db",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("POSTGRES_HOST", raising=False)


@pytest.fixture
def create_pool(db, monkeypatch):
    calls = []

    async def fake_create_pool(**kwargs):
        calls.append(kwargs)
        return FakePool()

    monkeypatch.setattr(db.asyncpg, "create_pool", fake_create_pool)
    return calls


@pytest.mark.parametrize("missing", ["POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"])
async def test_init_db_pool_requires_env(db, pg_env, create_pool, monkeypatch, missing):
    monkeypatch.delenv(missing)

    with pytest.raises(ValueError, match="Missing required Postgres environment variables"):
        await db.init_db_pool()
    assert create_pool == []


async def test_init_db_pool_creates_pool_once(db, pg_env, create_pool):
    first = await db.init_db_pool()
    second = await db.init_db_pool()

    assert first is second is db.db_pool
    assert create_pool == [{
        "user": "placeholder_user", "password": "placeholder_password",
        "database": "placeholder_db", "host": "localhost",
        "min_size": 5, "max_size": 20,
    }]


async def test_init_db_pool_does_not_print_password(db, pg_env, create_pool, capsys):
    await db.init_db_pool()

    assert "placeholder_password" not in capsys.readouterr().out


async def test_shutdown_closes_pool(pg, db, pg_env, create_pool):
    await pg.initialize_db()
    pool = db.db_pool

    await pg.shutdown()

    assert pool.closed
    assert db.db_pool is None


async def test_shutdown_without_pool_is_a_no_op(pg, db):
    assert db.db_pool is None

    await pg.shutdown()  # must not raise
