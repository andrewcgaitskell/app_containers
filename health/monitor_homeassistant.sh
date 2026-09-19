#!/usr/bin/env bash
# =============================================================================
# Home Assistant Health Monitor & Auto-Restart
# =============================================================================
# Purpose:   Checks if Home Assistant is responsive every 5 minutes.
#            Restarts the container if the API doesn't respond for several
#            consecutive checks in a row (avoids restarting on a brief blip).
#            Keeps the log file from growing forever.
#
# Runs in:   Dedicated Docker container ("health")
# Log file:  /var/log/monitor.log  → mounted to host at /opt/data/health/monitor.log
#
# Requires:  /var/run/docker.sock mounted into this container, and the
#            docker CLI installed in its image, so `docker restart` works.
# =============================================================================

# ────────────────────────────────────────────────
#  CONFIGURATION
# ────────────────────────────────────────────────

CONTAINER_NAME="homeassistant"                          # Name of the HA container to monitor/restart
HEALTH_URL="http://localhost:8123/manifest.json"        # Lightweight, unauthenticated HA endpoint

LOGFILE="/var/log/monitor.log"                          # Where we write logs (persisted via volume)

MAX_LOG_SIZE=$((20 * 1024 * 1024))                      # 20 MB – when to trim the log
KEEP_LINES=2500                                         # Keep roughly the last 2500 lines when trimming

CHECK_INTERVAL=300                                      # Seconds between checks - 5 minutes
MAX_FAILS=3                                             # Consecutive failures required before restarting
POST_RESTART_COOLDOWN=90                                # Seconds to wait after a restart before resuming normal checks

# ────────────────────────────────────────────────
#  SETUP
# ────────────────────────────────────────────────

mkdir -p "$(dirname "$LOGFILE")"                        # Ensure log directory exists

FAIL_COUNT=0

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S')  $*" >> "$LOGFILE"
}

trim_log_if_needed() {
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
}

# Clean shutdown on docker stop / SIGINT
trap 'log "Stopping Home Assistant monitor"; exit 0' SIGTERM SIGINT

# ────────────────────────────────────────────────
#  MAIN MONITORING LOOP
# ────────────────────────────────────────────────

log "Starting Home Assistant monitor (checking every ${CHECK_INTERVAL}s, restart after ${MAX_FAILS} consecutive failures)"

while true; do
    log "Checking status of container '${CONTAINER_NAME}'..."

    if ! curl -s --fail --connect-timeout 5 "$HEALTH_URL" > /dev/null; then
        FAIL_COUNT=$((FAIL_COUNT + 1))
        log "WARNING: Health check failed (${FAIL_COUNT}/${MAX_FAILS})"

        if (( FAIL_COUNT >= MAX_FAILS )); then
            log "ERROR: Home Assistant unresponsive after ${MAX_FAILS} consecutive checks → restarting container '${CONTAINER_NAME}'"
            docker restart "$CONTAINER_NAME" >> "$LOGFILE" 2>&1
            log "Restart command executed"
            FAIL_COUNT=0

            trim_log_if_needed
            log "Cooling down for ${POST_RESTART_COOLDOWN}s to allow Home Assistant to fully start"
            sleep "$POST_RESTART_COOLDOWN"
            continue
        fi
    else
        if (( FAIL_COUNT > 0 )); then
            log "Home Assistant is responding normally again"
        else
            log "Home Assistant is responding normally"
        fi
        FAIL_COUNT=0
    fi

    trim_log_if_needed
    sleep "$CHECK_INTERVAL"
done
