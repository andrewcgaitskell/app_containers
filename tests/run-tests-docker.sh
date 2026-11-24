#!/usr/bin/env bash
# Build the test image and run the quart_app tests in an isolated container,
# saving a timestamped report under test-results/.
#
# Installed root-owned as /usr/local/bin/run-app-tests (see tests/README.md)
# so an agent can run exactly this, and nothing else, via sudo.
# Takes no arguments on purpose: every Docker flag is fixed here.
set -euo pipefail

REPO=/opt/data/app_containers
IMAGE=app-containers-tests:latest
RESULTS="$REPO/test-results"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
REPORT="$RESULTS/$STAMP.txt"

if [ "$#" -ne 0 ]; then
    echo "usage: $(basename "$0")   (no arguments)" >&2
    exit 2
fi

mkdir -p "$RESULTS"

COMMIT=$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo unknown)
if [ -n "$(git -C "$REPO" status --porcelain -- quart_app health postgres/quart tests pytest.ini 2>/dev/null)" ]; then
    COMMIT="$COMMIT (+uncommitted changes)"
fi

{
    echo "Test run:   $STAMP"
    echo "Commit:     $COMMIT"
    echo "Image:      $IMAGE (python:3.11-slim)"
    echo "Command:    pytest -v -rA  (in container, no network)"
    echo "----------------------------------------------------------------"
} > "$REPORT"

# Build: context is quart_app/ only, so nothing else in the repo
# (compose/.env, data/, ...) is sent to the Docker daemon.
if ! docker build -q -t "$IMAGE" -f "$REPO/tests/Dockerfile" "$REPO/quart_app" >> "$REPORT" 2>&1; then
    echo "RESULT: BUILD FAILED" | tee -a "$REPORT"
    echo "$STAMP  $COMMIT  BUILD FAILED" >> "$RESULTS/history.txt"
    cp "$REPORT" "$RESULTS/latest.txt"
    exit 1
fi

# Run: no network, no capabilities, read-only filesystem; code and tests
# mounted read-only; only test-results/ is writable.
# Run as the owner of test-results/ so reports are writable without
# extra capabilities and stay readable by that user.
RUN_AS=$(stat -c '%u:%g' "$RESULTS")

set +e
docker run --rm \
    --user "$RUN_AS" \
    --network none \
    --cap-drop ALL \
    --security-opt no-new-privileges \
    --read-only --tmpfs /tmp:exec \
    --memory 512m --pids-limit 256 \
    -v "$REPO/quart_app:/work/quart_app:ro" \
    -v "$REPO/tests:/work/tests:ro" \
    -v "$REPO/health:/work/health:ro" \
    -v "$REPO/postgres/quart:/work/postgres/quart:ro" \
    -v "$REPO/pytest.ini:/work/pytest.ini:ro" \
    -v "$RESULTS:/results" \
    "$IMAGE" --junitxml="/results/$STAMP.xml" 2>&1 | tee -a "$REPORT"
STATUS=${PIPESTATUS[0]}
set -e

SUMMARY=$(grep -E '^=+ .*(passed|failed|error).* =+$' "$REPORT" | tail -1 | tr -d '=' | xargs || true)
if [ "$STATUS" -eq 0 ]; then RESULT=PASSED; else RESULT="FAILED (exit $STATUS)"; fi

echo "RESULT: $RESULT" | tee -a "$REPORT"
echo "$STAMP  $COMMIT  $RESULT  ${SUMMARY:-no summary}" >> "$RESULTS/history.txt"
cp "$REPORT" "$RESULTS/latest.txt"

exit "$STATUS"
