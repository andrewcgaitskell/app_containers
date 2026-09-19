#!/usr/bin/env bash
# =============================================================================
# Internet Speed Test (single-pass, cron-invoked every 10 minutes)
# =============================================================================
# Purpose:   Runs speedtest-cli against a known-good pinned server (falling
#            back through a short list if one is dead) and writes the full
#            raw JSON result into a Postgres table for later querying.
#
# Requires:  POSTGRES_HOST / POSTGRES_PORT / POSTGRES_DB / POSTGRES_USER /
#            POSTGRES_PASSWORD set in the container's environment (compose).
#
# Log file:  /var/log/speedtest.log  (run/error log only — data lives in DB)
# =============================================================================

##### NOT IMPLEMENTED YET ######

set -u

LOGFILE="/var/log/speedtest.log"

# Ordered list of server IDs to try (see `speedtest-cli --secure --list`).
# The first one that returns a non-zero download result is used.
SERVER_IDS=(51395 71586 65170)

mkdir -p "$(dirname "$LOGFILE")"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S')  $*" >> "$LOGFILE"
}

run_test() {
    speedtest-cli --secure --json --server "$1" 2>>"$LOGFILE"
}

log "Running speed test..."

result=""
used_server_id=""

for sid in "${SERVER_IDS[@]}"; do
    candidate=$(run_test "$sid")
    candidate_download=$(echo "$candidate" | python3 -c "import sys,json; print(json.load(sys.stdin).get('download', 0))" 2>>"$LOGFILE")
    if [[ -n "$candidate_download" ]] && python3 -c "exit(0 if float('$candidate_download') > 0 else 1)" 2>/dev/null; then
        result="$candidate"
        used_server_id="$sid"
        break
    else
        log "Server $sid returned zero/invalid result, trying next..."
    fi
done

if [[ -z "$result" ]]; then
    log "ERROR: speedtest-cli returned no usable result from any configured server"
    exit 1
fi

# Human-readable one-liner for quick tailing — full detail goes to Postgres
download_mbps=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(round(d['download']/1_000_000, 2))" 2>>"$LOGFILE")
upload_mbps=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(round(d['upload']/1_000_000, 2))" 2>>"$LOGFILE")
log "Result: ${download_mbps} Mbps down / ${upload_mbps} Mbps up (server id ${used_server_id})"

# Write the full raw JSON result into Postgres. Passed via stdin (not as a
# shell argument) so there's no quoting/escaping risk with the JSON content,
# and the DB driver parameterizes the insert so no manual SQL-escaping is
# needed either.
echo "$result" | python3 - "$used_server_id" <<'PYEOF' 2>>"$LOGFILE"
import sys
import json
import os
import psycopg2

server_id = sys.argv[1]
raw_json = sys.stdin.read()

# Validate it's real JSON before writing — fail loudly rather than storing garbage
parsed = json.loads(raw_json)

conn = psycopg2.connect(
    host=os.environ.get("POSTGRES_HOST", "localhost"),
    port=os.environ.get("POSTGRES_PORT", "5432"),
    dbname=os.environ["POSTGRES_DB"],
    user=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
)
conn.autocommit = True

with conn.cursor() as cur:
    cur.execute("""
        CREATE SCHEMA IF NOT EXISTS health;
        CREATE TABLE IF NOT EXISTS health.speedtest_log (
            id SERIAL PRIMARY KEY,
            checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            server_id TEXT,
            download_mbps NUMERIC,
            upload_mbps NUMERIC,
            raw_json JSONB NOT NULL
        );
    """)
    cur.execute(
        """
        INSERT INTO health.speedtest_log (server_id, download_mbps, upload_mbps, raw_json)
        VALUES (%s, %s, %s, %s)
        """,
        (
            server_id,
            round(parsed["download"] / 1_000_000, 2),
            round(parsed["upload"] / 1_000_000, 2),
            json.dumps(parsed),
        ),
    )

conn.close()
print("OK")
PYEOF

if [[ $? -ne 0 ]]; then
    log "ERROR: Failed to write speedtest result to Postgres — see above for traceback"
    exit 1
fi

log "Result written to health.speedtest_log"
