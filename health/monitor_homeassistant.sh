#!/bin/bash

# Important: Set the name of the container to monitor
CONTAINER_NAME="homeassistant"

# Health check URL (modify this if Home Assistant is configured on a different port)
# use container name as hostname
HEALTH_URL="http://home_assistant:8123"

# Log file (inside the container)
LOGFILE="/var/log/monitor.log"

# Ensure the log directory exists
mkdir -p /var/log

while true; do
    echo "$(date): Checking Home Assistant container status..." >> $LOGFILE

    # Perform the health check
    if ! curl -s "$HEALTH_URL" > /dev/null; then
        echo "$(date): Home Assistant container is unresponsive. Restarting..." >> $LOGFILE
        docker restart $CONTAINER_NAME >> $LOGFILE 2>&1
    else
        echo "$(date): Home Assistant is running fine." >> $LOGFILE
    fi

    # Sleep for 30 seconds before re-checking
    sleep 30
done
