#!/usr/bin/env bash
# =============================================================================
# Internet Speed Test (single-pass, cron-invoked every 10 minutes)
# =============================================================================
# Purpose:   Runs speedtest-cli and appends the result to a CSV log.
#
# Note on server selection: speedtest-cli's "best server" auto-pick can
# land on a dead/unreachable candidate (returns 0.00 Mbit/s and a sentinel
# ~1,800,000ms "ping" rather than failing cleanly). Rather than trusting
# auto-selection, this tries a short list of server IDs in order and uses
# the first one that returns a real (non-zero) result.
#
# Set PRIMARY_SERVER_ID below once you've identified a reliable nearby
# server via: speedtest-cli --secure --list | head -20
#
# Log file:  /var/log/speedtest.log        (run/error log)
# Data file: /opt/data/health/speedtest.csv (persisted via volume)
# =============================================================================

set -u

LOGFILE="/var/log/speedtest.log"
CSV_FILE="/opt/data/health/speedtest.csv"

# Ordered list of server IDs to try. Leave empty to fall back to
# speedtest-cli's own auto-selection (less reliable — see note above).
# Fill in with `speedtest-cli --secure --list` output, e.g. SERVER_IDS=(12345 67890)
SERVER_IDS=(51395 71586 65170)

mkdir -p "$(dirname "$LOGFILE")" "$(dirname "$CSV_FILE")"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S')  $*" >> "$LOGFILE"
}

if [ ! -f "$CSV_FILE" ]; then
    echo "timestamp,download_mbps,upload_mbps,ping_ms,server,isp" > "$CSV_FILE"
fi

run_test() {
    local server_flag=()
    if [[ -n "${1:-}" ]]; then
        server_flag=(--server "$1")
    fi
    speedtest-cli --secure --json "${server_flag[@]}" 2>>"$LOGFILE"
}

log "Running speed test..."

result=""
used_server_id=""

if [ ${#SERVER_IDS[@]} -eq 0 ]; then
    # No pinned servers configured — fall back to auto-selection
    result=$(run_test "")
else
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
fi

if [[ -z "$result" ]]; then
    log "ERROR: speedtest-cli returned no usable result from any configured server"
    exit 1
fi

download_mbps=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(round(d['download']/1_000_000, 2))" 2>>"$LOGFILE")
upload_mbps=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(round(d['upload']/1_000_000, 2))" 2>>"$LOGFILE")
ping_ms=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(round(d['ping'], 1))" 2>>"$LOGFILE")
server=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['server']['sponsor'])" 2>>"$LOGFILE")
isp=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('client', {}).get('isp', 'unknown'))" 2>>"$LOGFILE")

if [[ -z "$download_mbps" || "$download_mbps" == "0.0" ]]; then
    log "ERROR: All attempted servers returned zero. Raw result: $result"
    exit 1
fi

timestamp=$(date '+%Y-%m-%d %H:%M:%S')
echo "${timestamp},${download_mbps},${upload_mbps},${ping_ms},${server},${isp}" >> "$CSV_FILE"

log "Result: ${download_mbps} Mbps down / ${upload_mbps} Mbps up / ${ping_ms} ms ping (server: ${server}${used_server_id:+, id $used_server_id})"
