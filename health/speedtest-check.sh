#!/usr/bin/env bash
# =============================================================================
# Internet Speed Test (single-pass, cron-invoked every 10 minutes)
# =============================================================================
# Purpose:   Runs a speedtest and appends the result to a CSV log.
# Requires:  speedtest-cli (pip package) installed in the image.
# Log file:  /var/log/speedtest.log        (run/error log)
# Data file: /opt/data/health/speedtest.csv (persisted via volume)
# =============================================================================

set -u

LOGFILE="/var/log/speedtest.log"
CSV_FILE="/var/log/speedtest.csv"

mkdir -p "$(dirname "$LOGFILE")" "$(dirname "$CSV_FILE")"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S')  $*" >> "$LOGFILE"
}

# Write CSV header once, if the file doesn't exist yet
if [ ! -f "$CSV_FILE" ]; then
    echo "timestamp,download_mbps,upload_mbps,ping_ms,server" > "$CSV_FILE"
fi

log "Running speed test..."

# --secure avoids some mixed-content server issues; --json gives structured output
result=$(speedtest-cli --secure --json 2>>"$LOGFILE")

if [[ -z "$result" ]]; then
    log "ERROR: speedtest-cli returned no output"
    exit 1
fi

download_mbps=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(round(d['download']/1_000_000, 2))" 2>>"$LOGFILE")
upload_mbps=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(round(d['upload']/1_000_000, 2))" 2>>"$LOGFILE")
ping_ms=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(round(d['ping'], 1))" 2>>"$LOGFILE")
server=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['server']['sponsor'])" 2>>"$LOGFILE")

if [[ -z "$download_mbps" || -z "$upload_mbps" ]]; then
    log "ERROR: Failed to parse speedtest-cli output"
    exit 1
fi

timestamp=$(date '+%Y-%m-%d %H:%M:%S')
echo "${timestamp},${download_mbps},${upload_mbps},${ping_ms},${server}" >> "$CSV_FILE"

log "Result: ${download_mbps} Mbps down / ${upload_mbps} Mbps up / ${ping_ms} ms ping (server: ${server})"
