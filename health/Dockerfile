# Health container — runs all automated checks (HA monitor, Postgres dump
# trigger, internet speed test) on their own schedules via cron.
FROM docker.io/debian:bookworm-slim

# cron        — job scheduler, run in foreground as PID 1
# curl        — used by ha-health-monitor.sh and pg-dump-trigger.sh
# docker.io   — provides the `docker` CLI so ha-health-monitor.sh can
#               `docker restart` the HA container (needs the socket mounted)
# python3 / python3-pip — used to run speedtest-cli (pinned >=2.1.3, which
#               fixes a ValueError bug present in 2.1.2 that produced
#               bogus 0.0 Mbps / garbage-latency results)
RUN apt-get update && apt-get install -y \
    cron \
    curl \
    docker.io \
    python3 \
    python3-pip \
    python3-venv \
    && apt-get clean && rm -rf /var/lib/apt/lists/*


set -euo pipefail
 
VENV_DIR="${VENV_DIR:-/opt/net-monitor/venv}"
 
echo "Creating virtual environment at ${VENV_DIR} ..."
sudo mkdir -p "$(dirname "$VENV_DIR")"
sudo chown "$(id -u):$(id -g)" "$(dirname "$VENV_DIR")"
 
python3 -m venv "$VENV_DIR"
 
echo "Installing packages into the venv ..."
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install speedtest-cli paho-mqtt
 
echo
echo "Done. Venv created at: ${VENV_DIR}"
echo "speedtest-cli path:    ${VENV_DIR}/bin/speedtest-cli"
echo "python path:            ${VENV_DIR}/bin/python3"
echo
echo "If you used a custom VENV_DIR, make sure net-speedtest-daily.sh"
echo "and mqtt_publish.py point at the same path."


# Scripts
COPY ha-health-monitor.sh /scripts/ha-health-monitor.sh
COPY pg-dump-trigger.sh /scripts/pg-dump-trigger.sh
COPY speedtest-check.sh /scripts/speedtest-check.sh
RUN chmod +x /scripts/*.sh

# Crontab
COPY health-crontab /etc/cron.d/health-crontab
RUN chmod 0644 /etc/cron.d/health-crontab \
    && crontab /etc/cron.d/health-crontab

# Ensure log/state directories exist so scripts don't fail on first run
RUN mkdir -p /var/log /var/lib/health /opt/data/health

# cron -f keeps the process in the foreground so Docker can track/restart it
ENTRYPOINT ["cron", "-f"]

