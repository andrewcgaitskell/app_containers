# Changelog

Notable changes to this repository, newest first.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).
History before November 2026 is in `git log`.

## [Unreleased]

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
