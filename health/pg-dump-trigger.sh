#!/usr/bin/env bash
# =============================================================================
# Postgres Data Dump Trigger (single-pass, cron-invoked)
# =============================================================================
# Purpose:   Hits the Quart app's /trigger_data_dump endpoint once daily.
# Log file:  /var/log/data-dump-trigger.log
# =============================================================================

set -u

TRIGGER_URL="http://localhost:8090/trigger_data_dump"
LOGFILE="/var/log/data-dump-trigger.log"

mkdir -p "$(dirname "$LOGFILE")"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S')  $*" >> "$LOGFILE"
}

log "Triggering data dump: $TRIGGER_URL"

response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST --max-time 30 "$TRIGGER_URL" 2>&1)
http_status=$(echo "$response" | grep -o 'HTTP_STATUS:[0-9]*' | cut -d: -f2)
body=$(echo "$response" | sed '/HTTP_STATUS:/d')

if [[ "$http_status" == "200" ]]; then
    log "Data dump trigger succeeded (HTTP $http_status). Response: $body"
else
    log "WARNING: Data dump trigger returned HTTP ${http_status:-unknown}. Response: $body"
fi
