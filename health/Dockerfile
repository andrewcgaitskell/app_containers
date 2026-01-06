# Start with a lightweight base image
FROM bash:latest

# Install curl for health checks
RUN apk --no-cache add curl

# Copy the monitoring script into the container
COPY monitor_homeassistant.sh /usr/local/bin/monitor_homeassistant.sh

# Make the script executable
RUN chmod +x /usr/local/bin/monitor_homeassistant.sh

# Set the monitoring script as the default command
CMD ["/usr/local/bin/monitor_homeassistant.sh"]
