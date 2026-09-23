#!/bin/bash
#
# net-speedtest-daily.sh
#
# Runs a daily download/upload speed test and publishes the results to
# MQTT. Publishes a retained "latest reading" message every run, and a
# separate anomaly message only when speeds fall below configured
# thresholds (or the test fails outright).
#
# Intended crontab entry (once daily, e.g. 03:17):
#   17 3 * * * /path/to/net-speedtest-daily.sh >> /var/log/net-speedtest-daily.log 2>&1
#
# Requires: speedtest-cli and mosquitto_pub (mosquitto-clients), plus jq
#   sudo apt install speedtest-cli mosquitto-clients jq
#
# Note: speedtest-cli (the open-source Python tool) is used here because
# it's simple to parse. If you prefer Ookla's official "speedtest" CLI
# instead, its --format=json output differs slightly (fields are named
# download.bandwidth / upload.bandwidth in bytes/sec, ping.latency, and
# results.url) — swap the extraction section marked below accordingly.

set -u

### ---- Configuration ---------------------------------------------------

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
    [[ "${3:-}" == "retain" ]] && retain_flag=(-r)

    local auth_args=()
    if [[ -n "$MQTT_USER" ]]; then
        auth_args=(-u "$MQTT_USER" -P "$MQTT_PASS")
    fi

    mosquitto_pub -h "$MQTT_HOST" -p "$MQTT_PORT" "${auth_args[@]}" \
        -t "$topic" -m "$payload" "${retain_flag[@]}"
}

timestamp="$(date -Iseconds)"

### ---- Run the speed test -------------------------------------------------

raw_json="$(speedtest-cli --json 2>/tmp/speedtest-daily-error.log)"
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
download_bps="$(jq -r '.download' <<<"$raw_json")"
upload_bps="$(jq -r '.upload' <<<"$raw_json")"
ping_ms="$(jq -r '.ping' <<<"$raw_json")"
server_name="$(jq -r '.server.name // "unknown"' <<<"$raw_json")"
server_sponsor="$(jq -r '.server.sponsor // "unknown"' <<<"$raw_json")"

# Convert to Mbps (rounded to 1 decimal place).
download_mbps="$(awk -v b="$download_bps" 'BEGIN { printf "%.1f", b / 1000000 }')"
upload_mbps="$(awk -v b="$upload_bps" 'BEGIN { printf "%.1f", b / 1000000 }')"
ping_ms_rounded="$(awk -v p="$ping_ms" 'BEGIN { printf "%.1f", p }')"

result_payload=$(jq -n \
    --arg ts "$timestamp" \
    --arg dl "$download_mbps" \
    --arg ul "$upload_mbps" \
    --arg ping "$ping_ms_rounded" \
    --arg server "$server_name" \
    --arg sponsor "$server_sponsor" \
    '{timestamp:$ts, download_mbps:($dl|tonumber), upload_mbps:($ul|tonumber), ping_ms:($ping|tonumber), server:$server, sponsor:$sponsor}')

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

    anomaly_payload=$(jq -n \
        --arg ts "$timestamp" \
        --arg reasons "$joined_reasons" \
        --arg dl "$download_mbps" \
        --arg ul "$upload_mbps" \
        --arg ping "$ping_ms_rounded" \
        '{type:"speedtest_anomaly", reasons:$reasons, download_mbps:($dl|tonumber), upload_mbps:($ul|tonumber), ping_ms:($ping|tonumber), timestamp:$ts}')

    mqtt_publish "$MQTT_TOPIC_ANOMALY" "$anomaly_payload"
else
    log "No anomalies detected."
fi
