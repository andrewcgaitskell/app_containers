docker compose -f ../ha_compose.yml build health
docker compose -f ../ha_compose.yml up -d --no-deps health
