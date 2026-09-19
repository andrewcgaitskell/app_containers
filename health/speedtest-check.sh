#!/usr/bin/env bash
# =============================================================================
# Internet Speed Test (single-pass, cron-invoked every 10 minutes)
# =============================================================================
# Purpose:   Runs speedtest-cli (pip package, pinned >=2.1.3 — this version
#            fixes a ValueError bug in 2.1.2 that produced bogus 0.0 Mbps /
#            garbage-latency results) and appends the result to a CSV log.
#
# Note:      Like any genuine speed test against an external server, this
#            necessarily reveals your public IP to that server, and
#            speedtest-cli additionally logs your ISP name/approx location
#            locally as part of its normal output. That's inherent to real
#            speed measurement, not a flaw specific to this tool.
#
# Log file:  /var/log/speedtest.log        (run/error log)
# Data file: /var/log/speedtest.csv (persisted via volume)
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
    echo "timestamp,download_mbps,upload_mbps,ping_ms,server,isp" > "$CSV_FILE"
fi

log "Running speed test..."

result=$(speedtest-cli --secure --json 2>>"$LOGFILE")

if [[ -z "$result" ]]; then
    log "ERROR: speedtest-cli returned no output"
    exit 1
fi

# speedtest-cli's JSON reports download/upload already in bits/sec —
# divide by 1,000,000 to get Mbps (no x8 needed, unlike byte-based tools)
download_mbps=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(round(d['download']/1_000_000, 2))" 2>>"$LOGFILE")
upload_mbps=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(round(d['upload']/1_000_000, 2))" 2>>"$LOGFILE")
ping_ms=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(round(d['ping'], 1))" 2>>"$LOGFILE")
server=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['server']['sponsor'])" 2>>"$LOGFILE")
isp=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('client', {}).get('isp', 'unknown'))" 2>>"$LOGFILE")

if [[ -z "$download_mbps" || -z "$upload_mbps" ]]; then
    log "ERROR: Failed to parse speedtest-cli output. Raw result: $result"
    exit 1
fi

timestamp=$(date '+%Y-%m-%d %H:%M:%S')
echo "${timestamp},${download_mbps},${upload_mbps},${ping_ms},${server},${isp}" >> "$CSV_FILE"

log "Result: ${download_mbps} Mbps down / ${upload_mbps} Mbps up / ${ping_ms} ms ping (server: ${server})"
