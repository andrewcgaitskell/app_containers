#!/bin/bash
#
# net-connectivity-check.sh
#
# Checks internet connectivity by pinging a small set of reliable hosts.
# Publishes state (up/down) to MQTT, but only "spams" a full anomaly
# message when the state changes or when connectivity is down, so a
# frequent cron schedule (e.g. every 5 minutes) doesn't flood the broker.
#
# Uses the dedicated Python venv (see net-speedtest-setup.sh) for MQTT
# publishing via paho-mqtt/mqtt_publish.py, so no system-wide
# mosquitto-clients package is required.
#
# Intended crontab entry (every 5 minutes):
#   */5 * * * * /path/to/net-connectivity-check.sh >> /var/log/net-connectivity-check.log 2>&1
#
# Requires: ping (usually preinstalled), plus the venv from
#   net-speedtest-setup.sh, and mqtt_publish.py alongside this script.

set -u

### ---- Configuration ---------------------------------------------------

# Location of the dedicated venv created by net-speedtest-setup.sh, and
# the mqtt_publish.py helper that ships alongside this script.
VENV_DIR="/opt/net-monitor/venv"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MQTT_PUBLISH_PY="${SCRIPT_DIR}/mqtt_publish.py"

VENV_PYTHON="${VENV_DIR}/bin/python3"

# Hosts to ping. Using more than one avoids false positives if a single
# host is temporarily unreachable/rate-limiting ICMP.
PING_HOSTS=("1.1.1.1" "8.8.8.8" "9.9.9.9")

# Number of ping attempts per host, and timeout (seconds) per attempt.
PING_COUNT=2
PING_TIMEOUT=3

# How many hosts must succeed for the connection to be considered "up".
MIN_HOSTS_UP=1

# MQTT broker settings.
MQTT_HOST="localhost"
MQTT_PORT=1883
MQTT_USER=""              # leave blank if not using auth
MQTT_PASS=""              # leave blank if not using auth
MQTT_TOPIC_STATE="net/connectivity/state"
MQTT_TOPIC_ANOMALY="net/connectivity/anomaly"

# File used to remember the last known state between cron runs.
STATE_FILE="/var/tmp/net-connectivity-last-state"

### ---- Helpers -----------------------------------------------------------

log() {
    echo "$(date -Iseconds) $*"
}

mqtt_publish() {
    local topic="$1"
    local payload="$2"
    local retain_flag=()
    [[ "${3:-}" == "retain" ]] && retain_flag=(--retain)

    local auth_args=()
    if [[ -n "$MQTT_USER" ]]; then
        auth_args=(--username "$MQTT_USER" --password "$MQTT_PASS")
    fi

    "$VENV_PYTHON" "$MQTT_PUBLISH_PY" \
        --host "$MQTT_HOST" --port "$MQTT_PORT" \
        --topic "$topic" --payload "$payload" \
        "${retain_flag[@]}" "${auth_args[@]}"
}

### ---- Sanity checks -------------------------------------------------------

if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "$(date -Iseconds) ERROR: venv not found at ${VENV_DIR}." >&2
    echo "Run net-speedtest-setup.sh first." >&2
    exit 1
fi

if [[ ! -f "$MQTT_PUBLISH_PY" ]]; then
    echo "$(date -Iseconds) ERROR: mqtt_publish.py not found at ${MQTT_PUBLISH_PY}." >&2
    exit 1
fi

### ---- Connectivity check -------------------------------------------------

hosts_up=0
hosts_total=${#PING_HOSTS[@]}
failed_hosts=()

for host in "${PING_HOSTS[@]}"; do
    if ping -c "$PING_COUNT" -W "$PING_TIMEOUT" "$host" >/dev/null 2>&1; then
        hosts_up=$((hosts_up + 1))
    else
        failed_hosts+=("$host")
    fi
done

if (( hosts_up >= MIN_HOSTS_UP )); then
    current_state="up"
else
    current_state="down"
fi

timestamp="$(date -Iseconds)"

### ---- State comparison and publishing ------------------------------------

previous_state="unknown"
if [[ -f "$STATE_FILE" ]]; then
    previous_state="$(cat "$STATE_FILE")"
fi

# Always publish a lightweight, retained "current state" message so any
# MQTT dashboard can show live status without waiting for an anomaly.
mqtt_publish "$MQTT_TOPIC_STATE" \
    "{\"state\":\"${current_state}\",\"hosts_up\":${hosts_up},\"hosts_total\":${hosts_total},\"timestamp\":\"${timestamp}\"}" \
    retain

if [[ "$current_state" == "down" ]]; then
    log "Connectivity DOWN (${hosts_up}/${hosts_total} hosts reachable). Failed: ${failed_hosts[*]}"
    mqtt_publish "$MQTT_TOPIC_ANOMALY" \
        "{\"type\":\"connectivity_down\",\"hosts_up\":${hosts_up},\"hosts_total\":${hosts_total},\"failed_hosts\":\"${failed_hosts[*]}\",\"timestamp\":\"${timestamp}\"}"
elif [[ "$previous_state" == "down" && "$current_state" == "up" ]]; then
    log "Connectivity RESTORED (${hosts_up}/${hosts_total} hosts reachable)."
    mqtt_publish "$MQTT_TOPIC_ANOMALY" \
        "{\"type\":\"connectivity_restored\",\"hosts_up\":${hosts_up},\"hosts_total\":${hosts_total},\"timestamp\":\"${timestamp}\"}"
else
    log "Connectivity OK (${hosts_up}/${hosts_total} hosts reachable)."
fi

echo "$current_state" > "$STATE_FILE"
