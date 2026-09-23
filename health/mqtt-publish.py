#!/usr/bin/env python3
"""
mqtt_publish.py

Small helper that publishes a single MQTT message using paho-mqtt, then
disconnects. Intended to be run with the venv's python interpreter from
net-speedtest-daily.sh, e.g.:

    /opt/net-monitor/venv/bin/python3 mqtt_publish.py \
        --host localhost --port 1883 \
        --topic net/speedtest/result --payload '{"download_mbps": 93.4}' \
        --retain

Exits 0 on success, non-zero on failure (connection error, publish timeout).
"""

import argparse
import sys

import paho.mqtt.publish as publish


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish a single MQTT message.")
    parser.add_argument("--host", default="localhost", help="MQTT broker hostname")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument("--topic", required=True, help="MQTT topic to publish to")
    parser.add_argument("--payload", required=True, help="Message payload (string, e.g. JSON)")
    parser.add_argument("--qos", type=int, default=0, choices=[0, 1, 2], help="MQTT QoS level")
    parser.add_argument("--retain", action="store_true", help="Set the MQTT retain flag")
    parser.add_argument("--username", default=None, help="MQTT username (optional)")
    parser.add_argument("--password", default=None, help="MQTT password (optional)")
    args = parser.parse_args()

    auth = None
    if args.username:
        auth = {"username": args.username, "password": args.password or ""}

    try:
        publish.single(
            topic=args.topic,
            payload=args.payload,
            qos=args.qos,
            retain=args.retain,
            hostname=args.host,
            port=args.port,
            auth=auth,
        )
    except Exception as exc:  # noqa: BLE001 - want to report any failure clearly
        print(f"MQTT publish failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
