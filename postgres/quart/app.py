from quart import Quart, Blueprint, jsonify, current_app
import os
import re
import logging
import subprocess
from datetime import datetime, timedelta
from datetime import timezone
import asyncio
import aiofiles
from zoneinfo import ZoneInfo


# Create a blueprint
backup_blueprint = Blueprint('backup', __name__)

# Where dumps and the last-backup timestamp are written (mounted volume).
BACKUP_DIR = os.environ.get("BACKUP_DIR", "/backups")


def _keep_days():
    """Days of dumps to keep, from BACKUP_KEEP_DAYS (default 30, minimum 1)."""
    try:
        days = int(os.environ.get("BACKUP_KEEP_DAYS", "30"))
    except ValueError:
        return 30
    return days if days >= 1 else 30


BACKUP_KEEP_DAYS = _keep_days()

# Only files this app creates are ever deleted: data_dump_* / data_data_only_*
# with a YYYYMMDD_HHMM timestamp and a .sql or .zip extension.
BACKUP_FILE_RE = re.compile(r"^(data_dump|data_data_only)_(\d{8}_\d{4})\.(sql|zip)$")


def cleanup_old_backups(now=None):
    """Delete dump files older than BACKUP_KEEP_DAYS.

    Age is taken from the timestamp in the filename. Files that don't match
    BACKUP_FILE_RE are never touched, and the newest backup of each type is
    always kept, however old. Errors are logged, never raised, so cleanup
    can't fail a backup. Returns the names of deleted files.
    """
    now = now or datetime.now()
    cutoff = now - timedelta(days=BACKUP_KEEP_DAYS)
    try:
        names = os.listdir(BACKUP_DIR)
    except OSError as e:
        logging.warning("Backup cleanup skipped: cannot list %s: %s", BACKUP_DIR, e)
        return []

    backups = []
    for name in names:
        match = BACKUP_FILE_RE.match(name)
        if not match:
            continue
        try:
            stamp = datetime.strptime(match.group(2), "%Y%m%d_%H%M")
        except ValueError:
            continue
        backups.append((name, match.group(1), stamp))

    newest = {}
    for _, kind, stamp in backups:
        newest[kind] = max(stamp, newest.get(kind, stamp))

    deleted = []
    for name, kind, stamp in sorted(backups):
        if stamp >= cutoff or stamp == newest[kind]:
            continue
        try:
            os.remove(os.path.join(BACKUP_DIR, name))
            deleted.append(name)
        except OSError as e:
            logging.warning("Backup cleanup could not delete %s: %s", name, e)

    if deleted:
        logging.info("Backup cleanup deleted %d file(s) older than %d days", len(deleted), BACKUP_KEEP_DAYS)
    return deleted

# Function to get or update the last backup timestamp
def get_last_backup_timestamp():
    timestamp_file = os.path.join(BACKUP_DIR, "last_backup_timestamp.txt")
    if os.path.exists(timestamp_file):
        with open(timestamp_file, 'r') as f:
            last_backup_str = f.read().strip()
        try:
            # Parse the string as a timezone-aware datetime
            return datetime.fromisoformat(last_backup_str)
        except ValueError:
            raise ValueError("Invalid timestamp format in the last backup file")
    # Default to Unix epoch as a timezone-aware datetime
    return datetime(1970, 1, 1, tzinfo=timezone.utc)

def update_last_backup_timestamp(timestamp):
    timestamp_file = os.path.join(BACKUP_DIR, "last_backup_timestamp.txt")
    with open(timestamp_file, 'w') as f:
        f.write(timestamp)

@backup_blueprint.route('/trigger_data_dump', methods=['POST'])
async def trigger_data_dump():
    try:
        # Backup directory
        backup_dir = BACKUP_DIR
        os.makedirs(backup_dir, exist_ok=True)

        # Define US timezone using zoneinfo
        # us_timezone = ZoneInfo("America/New_York")

        # Generate timestamped backup filename
        #current_time = datetime.now(us_timezone)
        current_time = datetime.now()
        timestamp = current_time.strftime("%Y%m%d_%H%M")
        backup_file = f"{backup_dir}/data_dump_{timestamp}.sql"
        zip_file = f"{backup_dir}/data_dump_{timestamp}.zip"

        env = os.environ.copy()
        env['PGUSER'] = "pythonuser"

        subprocess.run([
            "pg_dump",
            "-U", "pi5ha",
            "-d", "data",
            "-f", backup_file
        ], check=True, env=env)

        # Step 2: Zip the .sql file
        subprocess.run([
            "zip", "-j", zip_file, backup_file
        ], check=True)

        # (Optional) Step 3: Remove the raw .sql if you only want zip
        # os.remove(backup_file)

        # Step 4: Delete dumps older than BACKUP_KEEP_DAYS
        deleted = cleanup_old_backups()

        return jsonify({"message": f"Data backup successful: {backup_file}", "deleted": deleted}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@backup_blueprint.route('/trigger_data_data_only', methods=['POST'])
async def trigger_data_data_only():
    try:
        # Backup directory
        backup_dir = BACKUP_DIR
        os.makedirs(backup_dir, exist_ok=True)

        # Define US timezone using zoneinfo
        # us_timezone = ZoneInfo("America/New_York")

        # Generate timestamped backup filename
        #current_time = datetime.now(us_timezone)
        current_time = datetime.now()
        timestamp = current_time.strftime("%Y%m%d_%H%M")
        backup_file = f"{backup_dir}/data_data_only_{timestamp}.sql"
        zip_file = f"{backup_dir}/data_data_only_{timestamp}.zip"

        env = os.environ.copy()
        env['PGUSER'] = "pythonuser"

        subprocess.run([
            "pg_dump",
            "--data-only",  # Include data inserts only
            "-U", "pi5ha",
            "-d", "data",
            "-f", backup_file
        ], check=True, env=env)

        # Step 2: Zip the .sql file
        subprocess.run([
            "zip", "-j", zip_file, backup_file
        ], check=True)

        # (Optional) Step 3: Remove the raw .sql if you only want zip
        # os.remove(backup_file)

        # Step 4: Delete dumps older than BACKUP_KEEP_DAYS
        deleted = cleanup_old_backups()

        return jsonify({"message": f"Data backup successful: {backup_file}", "deleted": deleted}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Main Quart app
app = Quart(__name__)

# Register the blueprint
app.register_blueprint(backup_blueprint)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8090)
