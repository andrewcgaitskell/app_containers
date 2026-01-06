# Use Debian as the base image (includes /bin/bash)
FROM debian:latest

# Install curl for health checks and make sure bash is present
RUN apt-get update && apt-get install -y \
    curl \
    bash && \
    apt-get clean

# Copy the monitoring script into the container
COPY monitor_homeassistant.sh /usr/local/bin/monitor_homeassistant.sh

# Make the script executable
RUN chmod +x /usr/local/bin/monitor_homeassistant.sh

# Set the monitoring script as the default command
CMD ["/usr/local/bin/monitor_homeassistant.sh"]
