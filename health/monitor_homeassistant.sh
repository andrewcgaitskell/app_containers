#!/bin/bash

# Name of the Home Assistant container
CONTAINER_NAME="homeassistant"

# URL of the Home Assistant API (replace localhost if different)
HEALTH_URL="http://homeassistant:8123"

# Log file (inside the container for logs)
LOGFILE="/var/log/monitor.log"

# Ensure the log directory exists
mkdir -p /var/log

while true; do
    echo "$(date): Checking status of container '$CONTAINER_NAME' ..." >> $LOGFILE

    # Perform a health check on the Home Assistant API
    if ! curl -s "$HEALTH_URL" > /dev/null; then
        echo "$(date): Home Assistant is unresponsive. Restarting container '$CONTAINER_NAME' ..." >> $LOGFILE
        docker restart $CONTAINER_NAME >> $LOGFILE 2>&1
    else
        echo "$(date): Home Assistant is running fine." >> $LOGFILE
    fi

    # Wait before rechecking (e.g., every 30 seconds)
    sleep 30
done
