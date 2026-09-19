# Use a base image with PostgreSQL tools installed
FROM docker.io/postgres:18

# Install Python, venv, and required tools
RUN apt-get update && apt-get install -y \
    python3 python3-venv python3-pip \
    vim unzip zip \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Create a virtual environment and install Quart
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip and install Quart in the virtual environment
RUN pip install --upgrade pip && pip install quart asyncio asyncpg python-dotenv aiofiles

# Copy a custom entrypoint script
COPY docker-entrypoint-custom.sh /docker-entrypoint-custom.sh
RUN chmod +x /docker-entrypoint-custom.sh

# Create directories the entrypoint script needs at runtime
RUN mkdir -p /backups /logs

# Copy initialization scripts
COPY ./init.sql /docker-entrypoint-initdb.d/

# Expose PostgreSQL and HTTP ports
EXPOSE 5432 8080

# Use the custom entrypoint script
ENTRYPOINT ["/docker-entrypoint-custom.sh"]

# Mount the Python code as a volume
VOLUME ["/app"]
