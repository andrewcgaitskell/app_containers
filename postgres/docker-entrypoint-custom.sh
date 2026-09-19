#!/bin/bash

# Start PostgreSQL using the default entrypoint script in the background
docker-entrypoint.sh postgres &

# Capture the PID of the PostgreSQL process
POSTGRES_PID=$!

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to start..."
until pg_isready -d data -U pythonuser -h localhost -p 5432; do
    sleep 1
done

echo "PostgreSQL is ready. Starting Quart app..."

# Ensure the Python application is available in the mounted volume
if [[ ! -f /app/app.py ]]; then
    echo "Error: /app/app.py not found. Ensure the volume is correctly mounted."
    exit 1
fi

# Start the Quart app using the mounted code
/opt/venv/bin/python /app/app.py &

# Capture the PID of the Quart app
QUART_PID=$!

# Wait for both processes to complete (PostgreSQL and Quart app)
wait $POSTGRES_PID
wait $QUART_PID
