#!/usr/bin/env bash
# =============================================================================
# Home Assistant Health Monitor & Auto-Restart
# =============================================================================
# Purpose:   Checks if Home Assistant is responsive every 30 seconds.
#            Restarts the container if the API doesn't respond.
#            Keeps the log file from growing forever.
#
# Runs in:   Dedicated Docker container ("health")
# Log file:  /var/log/monitor.log  → mounted to host at /opt/data/health/monitor.log
# =============================================================================

# ────────────────────────────────────────────────
#  CONFIGURATION
# ────────────────────────────────────────────────

CONTAINER_NAME="homeassistant"                  # Name of the HA container to monitor/restart
HEALTH_URL="http://0.0.0.0:8123"                # HA API endpoint (localhost inside host network)

LOGFILE="/var/log/monitor.log"                  # Where we write logs (persisted via volume)

MAX_LOG_SIZE=$((20 * 1024 * 1024))              # 20 MB – when to trim the log
KEEP_LINES=2500                                 # Keep roughly the last 2500 lines when trimming

CHECK_INTERVAL=30                               # Seconds between checks

# ────────────────────────────────────────────────
#  SETUP
# ────────────────────────────────────────────────

mkdir -p "$(dirname "$LOGFILE")"                # Ensure log directory exists

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S')  $*" >> "$LOGFILE"
}

# ────────────────────────────────────────────────
#  MAIN MONITORING LOOP
# ────────────────────────────────────────────────

log "Starting Home Assistant monitor (checking every ${CHECK_INTERVAL}s)"

while true; do
    log "Checking status of container '${CONTAINER_NAME}'..."

    # Try to reach the HA API (5-second timeout)
    if ! curl -s --fail --connect-timeout 5 "$HEALTH_URL" > /dev/null; then
        log "ERROR: Home Assistant is unresponsive → restarting container '${CONTAINER_NAME}'"
        docker restart "$CONTAINER_NAME" >> "$LOGFILE" 2>&1
        log "Restart command executed"
    else
        log "Home Assistant is responding normally"
    fi

    # ────────────────────────────────────────────────
    #  Keep log file size under control
    # ────────────────────────────────────────────────
    if [ -f "$LOGFILE" ]; then
        current_size=$(stat -c %s "$LOGFILE" 2>/dev/null || echo 0)

        if (( current_size > MAX_LOG_SIZE )); then
            log "Log file too large (${current_size} bytes) → trimming to last ~${KEEP_LINES} lines"

            tail -n "$KEEP_LINES" "$LOGFILE" > "$LOGFILE.tmp" 2>/dev/null &&
            mv "$LOGFILE.tmp" "$LOGFILE" &&
            log "Log trimmed successfully" ||
            log "WARNING: Failed to trim log file"
        fi
    fi

    sleep "$CHECK_INTERVAL"
done
