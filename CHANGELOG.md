# Changelog

Notable changes to this repository, newest first.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).
History before November 2026 is in `git log`.

## [Unreleased]
### Added
- Backup cleanup in `postgres/quart/app.py`: after each successful dump,
  `data_dump_*` / `data_data_only_*` `.sql` and `.zip` files older than
  `BACKUP_KEEP_DAYS` (default 30) are deleted from `/backups`, based on the
  timestamp in the filename. The newest backup of each type is always kept
  and no other files are touched. Deleted names are returned in the
  response's `deleted` field (and so logged by `pg-dump-trigger.sh`).
  Takes effect when the Postgres container restarts.
- Test suite for `quart_app` under `tests/quart_app/` (routes, MQTT
  listener, DB writes, Home Assistant calls, temperature and presence
  plots). All external services are faked. Run with `python3 -m pytest`
  after `pip install -r quart_app/requirements-dev.txt`.
- `pytest.ini` and `quart_app/requirements-dev.txt`.
- Docker test runner: `tests/Dockerfile` and `tests/run-tests-docker.sh`
  run the tests in an isolated container (no network, read-only mounts) and
  write timestamped reports to `test-results/`. Setup in `tests/README.md`.
- Tests for the health container under `tests/health/`: behaviour of
  `ha-health-monitor.sh`, `pg-dump-trigger.sh`, `net-connectivity-check.sh`,
  `net-speedtest-daily.sh` and `mqtt-publish.py` with all external commands
  stubbed, plus checks that the Dockerfile, crontab and scripts fit together.
- Tests for the Postgres backup app (`postgres/quart/`) under
  `tests/postgres/`: both dump endpoints, failure handling, the
  last-backup timestamp helpers, and DB pool setup. `pg_dump`, `zip` and
  the pool are faked.
- Home Assistant automation "Andrew Bedroom Radiator night quiet"
  (`id: '1796256000001'`) in `/opt/data/home_assistant/config/automations.yaml`
  (outside this repository): sets `climate.andrew_bedroom_radiator`
  (SONOFF TRVZB) to `off` at 23:00 and back to `heat` at 07:00, so the
  valve motor doesn't buzz overnight. Backup of the previous file is
  `automations.yaml.bak` in the same directory.
- Home Assistant automation "Fermenting House heater"
  (`id: '1796256000002'`) in `/opt/data/home_assistant/config/automations.yaml`
  (outside this repository): holds the fermenting house at 22 °C by
  switching the 5 W heater pad plug (`switch.fermenting_house_heater_plug`) on
  below 21.7 °C and off above 22.3 °C, using the SONOFF probe
  (`sensor.fermenting_house_thermometer_temperature`). The heater is switched off
  if the probe is unavailable or silent for 2 hours. Re-checks every 5
  minutes and on HA start / automation reload.
- Temperature chart for Zigbee2MQTT devices in `quart_app`:
  `/temperature/zigbee/<friendly name>` charts the `temperature` readings
  stored for topic `zigbee2mqtt/<friendly name>`, using the same page as the
  Shelly chart. Optional `?target=22` draws a dashed setpoint line, e.g.
  `/temperature/zigbee/Fermenting%20House%20Thermometer?target=22`. The
  Shelly route `/temperature/<device>` is unchanged. Tests in
  `tests/quart_app/test_plots.py`.
- Claude Code skill `.claude/skills/quart-chart/SKILL.md`: how charts in
  `quart_app` get their data, the existing routes and template to reuse,
  and the testing and changelog steps for adding a new chart.
- Off-site backup: `backup/offsite-backup.sh` packs the data needed to
  rebuild the Pi (HA config, Zigbee2MQTT, OTBR, Matter, ESPHome,
  `compose/.env`, Blockly programs, Jupyter, latest Postgres dump),
  encrypts it with gpg and uploads it to Google Drive with rclone, keeping
  the newest 14. Setup, cron line and restore steps in `backup/README.md`.
  Not active until set up on the host. Tests in `tests/backup/`; the
  Docker test runner now mounts `backup/` (re-run its `install` line).

### Changed
- Health scripts: log, state and venv paths can be overridden by
  environment variables (`LOGFILE`, `STATE_DIR`, `MAX_LOG_SIZE`, `VENV_DIR`,
  `STATE_FILE`) for testing. Defaults are unchanged.
- Test runner mounts `health/` and allows executables in its `/tmp`.
- `postgres/quart/app.py`: backup directory can be overridden with
  `BACKUP_DIR` for testing; default is still `/backups`.
- Test runner also mounts `postgres/quart/` (read-only). Reinstall
  `/usr/local/bin/run-app-tests` to pick this up.

### Fixed
- `postgres/quart/app.py` ran `pg_dump -U pi5ha` with a hard-coded user
  (and a `PGUSER=pythonuser` that `-U` overrode). It now uses
  `POSTGRES_USER`, which compose passes in from `compose/.env`; if it is
  missing, the endpoint returns 500 without running `pg_dump`. Takes
  effect when the Postgres container restarts.
- `postgres/quart/app.py` never closed the DB pool on shutdown: it imported
  `db_pool` by value (always `None`). It now reads `db.db_pool`, closes it,
  and clears it. Takes effect when the Postgres container restarts.
- `POST /api/light/<entity>/set` returned an unhandled 500 when `state` was
  not a string (e.g. `1`, `null`) or the body was a JSON list; it now
  returns 400.
- `/ui/light/<entity>` inserted the entity ID from the URL into the page
  unescaped, so a crafted link could run script on the page. It is now
  HTML-escaped in the page text and safely encoded in the script.
- `net-speedtest-daily.sh` inserted the speedtest error text and server
  names into MQTT JSON payloads unescaped, so a quote or backslash produced
  invalid JSON. They are now escaped (control characters become spaces).
- The daily internet speed test was commented out in `health/health-crontab`
  and never ran. It is now scheduled daily at 03:17, logging to
  `/var/log/net-speedtest-daily.log`. Takes effect when the health
  container is rebuilt.
- The health image loaded `health-crontab` both into `/etc/cron.d/` and as
  root's user crontab. The user-crontab copy treated the `root` column as
  the command, so a failing duplicate of every job ran on schedule. The
  file is now installed only in `/etc/cron.d/`. Takes effect on rebuild.

### Removed
- Unused database connection pool in the Postgres backup app:
  `postgres/quart/db.py` deleted, and the startup/shutdown hooks that
  opened 5–20 idle connections removed from `app.py`. Backups only ever
  used `pg_dump`. The app no longer needs `POSTGRES_PASSWORD` at startup.
  Takes effect when the Postgres container restarts.
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
