# Pin to a specific, known-good Zigbee2MQTT release rather than "latest",
# so updates are deliberate (check current tags at
# https://hub.docker.com/r/koenkk/zigbee2mqtt/tags before bumping this).
FROM koenkk/zigbee2mqtt:1.42.0

# Basic container-level hardening
ENV NODE_ENV=production

# Simple healthcheck against the frontend (adjust the port if you change it
# in configuration.yaml). Requires the frontend to be enabled.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://127.0.0.1:8080 || exit 1

