#!/bin/bash
#
# net-connectivity-check.sh
#
# Checks internet connectivity by pinging a small set of reliable hosts.
# Publishes state (up/down) to MQTT, but only "spams" a full anomaly
# message when the state changes or when connectivity is down, so a
# frequent cron schedule (e.g. every 5 minutes) doesn't flood the broker.
#
# Intended crontab entry (every 5 minutes):
#   */5 * * * * /path/to/net-connectivity-check.sh >> /var/log/net-connectivity-check.log 2>&1
#
# Requires: ping, mosquitto_pub (from mosquitto-clients package)
#   sudo apt install mosquitto-clients

set -u

### ---- Configuration ---------------------------------------------------

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
    [[ "${3:-}" == "retain" ]] && retain_flag=(-r)

    local auth_args=()
    if [[ -n "$MQTT_USER" ]]; then
        auth_args=(-u "$MQTT_USER" -P "$MQTT_PASS")
    fi

    mosquitto_pub -h "$MQTT_HOST" -p "$MQTT_PORT" "${auth_args[@]}" \
        -t "$topic" -m "$payload" "${retain_flag[@]}"
}

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
