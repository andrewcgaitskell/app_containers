#!/usr/bin/env bash
# Nightly off-site backup of the data needed to rebuild this Pi.
#
# Packs the hard-to-recreate folders into one archive, encrypts it with a
# passphrase (gpg, AES256), uploads it to Google Drive with rclone and keeps
# the newest $KEEP archives there. Setup and restore: backup/README.md.
#
# Runs on the host as root (the data folders are root-owned), from cron:
#   30 6 * * * root /opt/data/app_containers/backup/offsite-backup.sh >> /var/log/offsite-backup.log 2>&1
set -euo pipefail

DATA_ROOT=${DATA_ROOT:-/opt/data}
PASSPHRASE_FILE=${PASSPHRASE_FILE:-/root/.config/offsite-backup/passphrase}
RCLONE_REMOTE=${RCLONE_REMOTE:-gdrive:pi-backups}
KEEP=${KEEP:-14}
WORK_DIR=${WORK_DIR:-/var/tmp/offsite-backup}

PREFIX=home-backup
STAMP=$(date +%Y%m%d_%H%M)
ARCHIVE="$PREFIX-$STAMP.tar.gz.gpg"

# Paths relative to $DATA_ROOT, so a restore is: decrypt | tar -x -C /opt/data
INCLUDE=(
    home_assistant/config
    zigbee2mqtt_data
    otbr/data
    matter/data
    esphome/config
    app_containers/compose/.env
    blockly/programs
    jupyter
)
EXCLUDE=(
    "home_assistant/config/home-assistant_v2.db*"   # history DB: large, unsafe to copy live
    "home_assistant/config/*.log*"
    "home_assistant/config/backups"
    "home_assistant/config/tts"
    "home_assistant/config/deps"
    "zigbee2mqtt_data/log"
    "esphome/config/.esphome"                       # build cache
    "jupyter/.ipynb_checkpoints"
)

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*"; }
die() { log "ERROR: $*"; exit 1; }

[ -s "$PASSPHRASE_FILE" ] || die "passphrase file $PASSPHRASE_FILE missing or empty"
[[ "$KEEP" =~ ^[1-9][0-9]*$ ]] || die "KEEP must be a positive integer, got '$KEEP'"
for cmd in tar gpg rclone; do
    command -v "$cmd" >/dev/null || die "$cmd not installed"
done

paths=()
for p in "${INCLUDE[@]}"; do
    if [ -e "$DATA_ROOT/$p" ]; then
        paths+=("$p")
    else
        log "WARNING: $DATA_ROOT/$p not found, skipped"
    fi
done

# Newest Postgres dump (written daily at 06:01 by the health container).
dump=$(cd "$DATA_ROOT" 2>/dev/null && ls -1 postgres_data/backups/data_dump_*.zip 2>/dev/null | sort | tail -n 1 || true)
if [ -z "$dump" ]; then
    dump=$(cd "$DATA_ROOT" 2>/dev/null && ls -1 postgres_data/backups/data_dump_*.sql 2>/dev/null | sort | tail -n 1 || true)
fi
if [ -n "$dump" ]; then
    paths+=("$dump")
else
    log "WARNING: no Postgres dump found in $DATA_ROOT/postgres_data/backups"
fi

[ "${#paths[@]}" -gt 0 ] || die "nothing to back up under $DATA_ROOT"

mkdir -p "$WORK_DIR"
chmod 700 "$WORK_DIR"
trap 'rm -f "$WORK_DIR/$ARCHIVE"' EXIT

excludes=()
for e in "${EXCLUDE[@]}"; do excludes+=("--exclude=$e"); done

log "Backing up: ${paths[*]}"
set +e
tar -czf - -C "$DATA_ROOT" "${excludes[@]}" "${paths[@]}" \
    | gpg --batch --yes --quiet --pinentry-mode loopback \
          --passphrase-file "$PASSPHRASE_FILE" \
          --symmetric --cipher-algo AES256 \
          --output "$WORK_DIR/$ARCHIVE"
statuses=("${PIPESTATUS[@]}")
set -e
# tar exit 1 = a file changed while being read (normal for live data).
if [ "${statuses[0]}" -gt 1 ]; then die "tar failed (exit ${statuses[0]})"; fi
if [ "${statuses[0]}" -eq 1 ]; then log "WARNING: some files changed while being read"; fi
[ "${statuses[1]}" -eq 0 ] || die "gpg encryption failed (exit ${statuses[1]})"

size=$(du -h "$WORK_DIR/$ARCHIVE" | cut -f1)
log "Uploading $ARCHIVE ($size) to $RCLONE_REMOTE"
rclone copy "$WORK_DIR/$ARCHIVE" "$RCLONE_REMOTE" || die "upload failed"

# Prune only after a successful upload; never touches other files.
mapfile -t old < <(rclone lsf --files-only --include "$PREFIX-*.tar.gz.gpg" "$RCLONE_REMOTE" \
    | grep -E "^$PREFIX-[0-9]{8}_[0-9]{4}\.tar\.gz\.gpg$" | sort | head -n -"$KEEP")
for f in "${old[@]}"; do
    log "Removing old backup $f"
    rclone deletefile "$RCLONE_REMOTE/$f" || log "WARNING: could not delete $f"
done

log "Done: $ARCHIVE"
