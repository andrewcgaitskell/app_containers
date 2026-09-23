#!/bin/bash
#
# net-speedtest-daily.sh
#
# Runs a daily download/upload speed test and publishes the results to
# MQTT. Publishes a retained "latest reading" message every run, and a
# separate anomaly message only when speeds fall below configured
# thresholds (or the test fails outright).
#
# Uses a dedicated Python venv (see net-speedtest-setup.sh) so
# speedtest-cli and paho-mqtt don't need to be installed system-wide.
#
# One-time setup:
#   ./net-speedtest-setup.sh
#
# Intended crontab entry (once daily, e.g. 03:17). Cron runs a minimal
# environment, so call scripts by full path — no venv activation needed,
# since we invoke the venv's binaries directly:
#   17 3 * * * /path/to/net-speedtest-daily.sh >> /var/log/net-speedtest-daily.log 2>&1

set -u

### ---- Configuration ---------------------------------------------------

# Location of the dedicated venv created by net-speedtest-setup.sh, and
# the mqtt_publish.py helper that ships alongside this script.
VENV_DIR="/opt/net-monitor/venv"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MQTT_PUBLISH_PY="${SCRIPT_DIR}/mqtt_publish.py"

VENV_PYTHON="${VENV_DIR}/bin/python3"
VENV_SPEEDTEST="${VENV_DIR}/bin/speedtest-cli"

# Expected minimums in Mbps. Set these to comfortably below your normal
# measured speed so ordinary variance doesn't trigger false alarms.
MIN_DOWNLOAD_MBPS=50
MIN_UPLOAD_MBPS=10

# Max acceptable ping (ms) to the speedtest server, as a rough latency check.
MAX_PING_MS=80

# MQTT broker settings.
MQTT_HOST="localhost"
MQTT_PORT=1883
MQTT_USER=""              # leave blank if not using auth
MQTT_PASS=""              # leave blank if not using auth
MQTT_TOPIC_RESULT="net/speedtest/result"
MQTT_TOPIC_ANOMALY="net/speedtest/anomaly"

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

if [[ ! -x "$VENV_PYTHON" || ! -x "$VENV_SPEEDTEST" ]]; then
    echo "$(date -Iseconds) ERROR: venv not found or incomplete at ${VENV_DIR}." >&2
    echo "Run net-speedtest-setup.sh first." >&2
    exit 1
fi

if [[ ! -f "$MQTT_PUBLISH_PY" ]]; then
    echo "$(date -Iseconds) ERROR: mqtt_publish.py not found at ${MQTT_PUBLISH_PY}." >&2
    exit 1
fi

timestamp="$(date -Iseconds)"

### ---- Run the speed test -------------------------------------------------

raw_json="$("$VENV_SPEEDTEST" --json 2>/tmp/speedtest-daily-error.log)"
exit_code=$?

if [[ $exit_code -ne 0 || -z "$raw_json" ]]; then
    error_msg="$(tr -d '\n' </tmp/speedtest-daily-error.log | tail -c 300)"
    log "Speedtest FAILED (exit code ${exit_code}): ${error_msg}"
    mqtt_publish "$MQTT_TOPIC_ANOMALY" \
        "{\"type\":\"speedtest_failed\",\"error\":\"${error_msg}\",\"timestamp\":\"${timestamp}\"}"
    exit 1
fi

# --- Extraction (speedtest-cli --json format) ---
# speedtest-cli reports download/upload in bits per second.
# Parsed with the venv's python (json module) so we don't add a jq dependency.
read -r download_bps upload_bps ping_ms server_name server_sponsor <<<"$("$VENV_PYTHON" - "$raw_json" <<'PYEOF'
import json, sys
data = json.loads(sys.argv[1])
server = data.get("server", {})
print(
    data.get("download", 0),
    data.get("upload", 0),
    data.get("ping", 0),
    (server.get("name") or "unknown").replace(" ", "_"),
    (server.get("sponsor") or "unknown").replace(" ", "_"),
)
PYEOF
)"

# Convert to Mbps (rounded to 1 decimal place).
download_mbps="$(awk -v b="$download_bps" 'BEGIN { printf "%.1f", b / 1000000 }')"
upload_mbps="$(awk -v b="$upload_bps" 'BEGIN { printf "%.1f", b / 1000000 }')"
ping_ms_rounded="$(awk -v p="$ping_ms" 'BEGIN { printf "%.1f", p }')"
server_name="${server_name//_/ }"
server_sponsor="${server_sponsor//_/ }"

result_payload="{\"timestamp\":\"${timestamp}\",\"download_mbps\":${download_mbps},\"upload_mbps\":${upload_mbps},\"ping_ms\":${ping_ms_rounded},\"server\":\"${server_name}\",\"sponsor\":\"${server_sponsor}\"}"

log "Speedtest result: download=${download_mbps}Mbps upload=${upload_mbps}Mbps ping=${ping_ms_rounded}ms server=\"${server_sponsor} (${server_name})\""

# Always publish the latest reading, retained, regardless of thresholds.
mqtt_publish "$MQTT_TOPIC_RESULT" "$result_payload" retain

### ---- Anomaly detection ---------------------------------------------------

anomalies=()

if awk -v v="$download_mbps" -v min="$MIN_DOWNLOAD_MBPS" 'BEGIN { exit !(v < min) }'; then
    anomalies+=("download ${download_mbps}Mbps below minimum ${MIN_DOWNLOAD_MBPS}Mbps")
fi

if awk -v v="$upload_mbps" -v min="$MIN_UPLOAD_MBPS" 'BEGIN { exit !(v < min) }'; then
    anomalies+=("upload ${upload_mbps}Mbps below minimum ${MIN_UPLOAD_MBPS}Mbps")
fi

if awk -v v="$ping_ms_rounded" -v max="$MAX_PING_MS" 'BEGIN { exit !(v > max) }'; then
    anomalies+=("ping ${ping_ms_rounded}ms above maximum ${MAX_PING_MS}ms")
fi

if (( ${#anomalies[@]} > 0 )); then
    joined_reasons="$(IFS='; '; echo "${anomalies[*]}")"
    log "ANOMALY detected: ${joined_reasons}"

    anomaly_payload="{\"type\":\"speedtest_anomaly\",\"reasons\":\"${joined_reasons}\",\"download_mbps\":${download_mbps},\"upload_mbps\":${upload_mbps},\"ping_ms\":${ping_ms_rounded},\"timestamp\":\"${timestamp}\"}"

    mqtt_publish "$MQTT_TOPIC_ANOMALY" "$anomaly_payload"
else
    log "No anomalies detected."
fi
