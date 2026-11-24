# Tests

Tests live here, in the repository. They are mounted read-only into a
throwaway Docker container to run, so nothing needs installing on the host.

## Layout
- `quart_app/` – tests for the Quart app. Postgres, MQTT and Home Assistant
  are replaced with in-memory fakes; no test talks to a live service.
- `health/` – tests for the health container's cron scripts and
  `mqtt-publish.py`. Scripts run in a temp directory with `curl`, `docker`,
  `ping`, `speedtest-cli` and the MQTT publisher replaced by recording stubs,
  so nothing is contacted, restarted or published.
- `Dockerfile` – test image (Python 3.11 + `quart_app/requirements-dev.txt`).
- `run-tests-docker.sh` – builds the image, runs the tests, writes results.

## Results (evidence)
Every run writes to `test-results/` in the repo root:
- `<UTC timestamp>.txt` – full report: time, git commit, verbose pytest output, result
- `<UTC timestamp>.xml` – JUnit XML of the same run
- `latest.txt` – copy of the most recent report
- `history.txt` – one line per run: time, commit, result, counts

## Running
As a human with Docker access:

    sudo /opt/data/app_containers/tests/run-tests-docker.sh

The container runs with no network, no capabilities, a read-only filesystem,
and only `test-results/` writable.

## Letting an agent run the tests (one-time setup, as root)
The agent user (`claude`) has no Docker access, and should not be added to the
`docker` group (that is equivalent to root). Instead, install the runner
root-owned outside the repo and allow just that one command via sudo:

    sudo install -o root -g root -m 0755 \
        /opt/data/app_containers/tests/run-tests-docker.sh /usr/local/bin/run-app-tests
    echo 'claude ALL=(root) NOPASSWD: /usr/local/bin/run-app-tests ""' \
        | sudo tee /etc/sudoers.d/claude-run-app-tests
    sudo chmod 0440 /etc/sudoers.d/claude-run-app-tests
    sudo visudo -cf /etc/sudoers.d/claude-run-app-tests

The `""` in the sudoers line means "no arguments allowed". The installed copy
is root-owned, so editing `tests/run-tests-docker.sh` in the repo does not
change what runs as root – re-run the `install` line after reviewing any change.

Run lightweight checks without Docker:

    python3 -m venv .venv && .venv/bin/pip install -r quart_app/requirements-dev.txt
    .venv/bin/python -m pytest
