# Changelog

Notable changes to this repository, newest first.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).
History before November 2026 is in `git log`.

## [Unreleased]
### Added
- Test suite for `quart_app` under `tests/quart_app/` (routes, MQTT
  listener, DB writes, Home Assistant calls, temperature and presence
  plots). All external services are faked. Run with `python3 -m pytest`
  after `pip install -r quart_app/requirements-dev.txt`.
- `pytest.ini` and `quart_app/requirements-dev.txt`.
- Docker test runner: `tests/Dockerfile` and `tests/run-tests-docker.sh`
  run the tests in an isolated container (no network, read-only mounts) and
  write timestamped reports to `test-results/`. Setup in `tests/README.md`.

### Fixed
- `POST /api/light/<entity>/set` returned an unhandled 500 when `state` was
  not a string (e.g. `1`, `null`) or the body was a JSON list; it now
  returns 400.

### Removed
- Debug `print` calls in `quart_app/blueprints/hass.py`.

## 2026-11-24
### Added
- `AGENTS.md` with working rules for coding agents; `CLAUDE.md` symlinks to it.
- `.claude/settings.json` permission rules for Claude Code.

### Changed
- `.gitignore` extended for Home Assistant secrets and runtime data
  (`secrets.yaml`, `.storage/`, keys, databases, backups, `data/**`).
- `AGENTS.md` rewritten: scoped to the repository's real location, added a
  repository layout, marked `data/` and tracked files that may hold
  credentials (`postgres/init.sql`, `postgres/pg_hba.conf`,
  `mosquitto/mosquitto.conf`) as sensitive, separated untrusted input from
  secrets, and listed the allowed local checks.
- `.claude/settings.json` rewritten: rule paths fixed (`./` for repo
  paths, `//` for absolute paths), reads and edits of secrets and `data/`
  denied, Docker/sudo/systemctl/network commands and `git commit`/`git push`
  blocked.

## 2026-11-14
### Changed
- `compose/ha_compose.yml` updated.

## 2026-11-07
### Added
- Presence page: `quart_app/blueprints/presence_plot.py` and
  `quart_app/templates/presence.html`.
- `health/rebuild.sh` helper for rebuilding the health container.

### Changed
- `quart_app/main.py` registers the presence page.
- `health/Dockerfile` updated.
