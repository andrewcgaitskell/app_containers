docker compose -f ha_compose.yml pull
docker compose -f ha_compose.yml build --no-cache
docker compose -f ha_compose.yml up -d --force-recreate
