#!/bin/bash
set -e

# Forward termination signals to child processes for clean shutdown
trap 'echo "Caught signal, shutting down..."; kill $POSTGRES_PID $QUART_PID 2>/dev/null; wait' SIGTERM SIGINT

# CORRECT: Append "$@" to forward your Docker Compose 'command' flags straight to the process
docker-entrypoint.sh postgres "$@" &
POSTGRES_PID=$!


# Wait for PostgreSQL to be ready, using the real runtime credentials
echo "Waiting for PostgreSQL to start..."
until pg_isready -d "$POSTGRES_DB" -U "$POSTGRES_USER" -h localhost -p 5432; do
    # Bail out early if Postgres itself has already died rather than looping forever
    if ! kill -0 "$POSTGRES_PID" 2>/dev/null; then
        echo "Error: PostgreSQL process exited before becoming ready."
        exit 1
    fi
    sleep 1
done

echo "PostgreSQL is ready. Starting Quart app..."

# Ensure the Python application is available in the mounted volume
if [[ ! -f /app/app.py ]]; then
    echo "Error: /app/app.py not found. Ensure the volume is correctly mounted."
    kill "$POSTGRES_PID" 2>/dev/null
    exit 1
fi

# Start the Quart app using the mounted code
/opt/venv/bin/python /app/app.py &
QUART_PID=$!

# Exit as soon as either process dies, so Docker's restart policy can react
wait -n "$POSTGRES_PID" "$QUART_PID"
EXIT_CODE=$?

echo "One of the processes exited (code $EXIT_CODE). Shutting down the other."
kill $POSTGRES_PID $QUART_PID 2>/dev/null
wait

exit $EXIT_CODE
