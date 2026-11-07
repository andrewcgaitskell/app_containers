#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/../compose/ha_compose.yml"

docker compose -f "$COMPOSE_FILE" build health
docker compose -f "$COMPOSE_FILE" up -d --no-deps health
