#!/usr/bin/env bash
# =============================================================================
# Home Assistant Health Check (single-pass, cron-invoked)
# =============================================================================
# Purpose:   Runs once per invocation (called every 5 minutes by cron).
#            Restarts the HA container after MAX_FAILS consecutive failures.
#            Fail count persists between runs via a small state file, since
#            each cron invocation is a fresh process with no memory of the last.
#
# Log file:  /var/log/monitor.log
# State file: /var/lib/health/ha_fail_count
#
# Requires:  /var/run/docker.sock mounted into this container, and the
#            docker CLI installed in its image, so `docker restart` works.
# =============================================================================

set -u

CONTAINER_NAME="homeassistant"
HEALTH_URL="http://localhost:8123/manifest.json"

LOGFILE="/var/log/monitor.log"
STATE_DIR="/var/lib/health"
FAIL_COUNT_FILE="${STATE_DIR}/ha_fail_count"
COOLDOWN_FLAG_FILE="${STATE_DIR}/ha_restart_cooldown_until"

MAX_LOG_SIZE=$((20 * 1024 * 1024))   # 20 MB – when to trim the log
KEEP_LINES=2500                      # Keep roughly the last 2500 lines when trimming

MAX_FAILS=3                          # Consecutive failures required before restarting
POST_RESTART_COOLDOWN=90             # Seconds after a restart to skip checks entirely

mkdir -p "$(dirname "$LOGFILE")" "$STATE_DIR"

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

# If we're still inside the post-restart cooldown window, skip this check entirely
now=$(date +%s)
if [ -f "$COOLDOWN_FLAG_FILE" ]; then
    cooldown_until=$(cat "$COOLDOWN_FLAG_FILE" 2>/dev/null || echo 0)
    if (( now < cooldown_until )); then
        log "Skipping check — within post-restart cooldown window (until $(date -d "@${cooldown_until}" '+%H:%M:%S'))"
        trim_log_if_needed
        exit 0
    else
        rm -f "$COOLDOWN_FLAG_FILE"
    fi
fi

# Read current fail count (defaults to 0 if file doesn't exist yet)
fail_count=$(cat "$FAIL_COUNT_FILE" 2>/dev/null || echo 0)
[[ "$fail_count" =~ ^[0-9]+$ ]] || fail_count=0

log "Checking status of container '${CONTAINER_NAME}'..."

if ! curl -s --fail --connect-timeout 5 "$HEALTH_URL" > /dev/null; then
    fail_count=$((fail_count + 1))
    log "WARNING: Health check failed (${fail_count}/${MAX_FAILS})"
    echo "$fail_count" > "$FAIL_COUNT_FILE"

    if (( fail_count >= MAX_FAILS )); then
        log "ERROR: Home Assistant unresponsive after ${MAX_FAILS} consecutive checks → restarting container '${CONTAINER_NAME}'"
        docker restart "$CONTAINER_NAME" >> "$LOGFILE" 2>&1
        log "Restart command executed"
        echo 0 > "$FAIL_COUNT_FILE"
        echo $(( $(date +%s) + POST_RESTART_COOLDOWN )) > "$COOLDOWN_FLAG_FILE"
    fi
else
    if (( fail_count > 0 )); then
        log "Home Assistant is responding normally again"
    else
        log "Home Assistant is responding normally"
    fi
    echo 0 > "$FAIL_COUNT_FILE"
fi

trim_log_if_needed
