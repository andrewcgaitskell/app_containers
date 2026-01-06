# Use a lightweight base image that supports Docker CLI installation
FROM alpine:latest

# Install bash, curl, and Docker CLI
RUN apk --no-cache add \
    bash \
    curl \
    docker-cli

# Copy the monitoring script to the container
COPY monitor_homeassistant.sh /usr/local/bin/monitor_homeassistant.sh

# Make the script executable
RUN chmod +x /usr/local/bin/monitor_homeassistant.sh

# Set the default command to execute the monitoring script
CMD ["/usr/local/bin/monitor_homeassistant.sh"]
