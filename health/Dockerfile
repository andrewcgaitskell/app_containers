# Health container — runs all automated checks (HA monitor, Postgres dump
# trigger, internet speed test) on their own schedules via cron.
FROM docker.io/debian:bookworm-slim

# cron        — job scheduler, run in foreground as PID 1
# curl        — used by ha-health-monitor.sh and pg-dump-trigger.sh
# docker.io   — provides the `docker` CLI so ha-health-monitor.sh can
#               `docker restart` the HA container (needs the socket mounted)
# python3     — used by speedtest-check.sh to parse JSON output
# python3-pip — to install speedtest-cli

RUN apt-get update && apt-get install -y \
    cron \
    curl \
    docker.io \
    python3 \
    python3-pip \
    && pip install --no-cache-dir --break-system-packages speedtest-cli \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

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
RUN mkdir -p /var/log /var/lib/health

# cron -f keeps the process in the foreground so Docker can track/restart it
ENTRYPOINT ["cron", "-f"]
