from quart import Quart, Blueprint, jsonify, current_app
import os
import subprocess
from datetime import datetime
from datetime import timezone
import asyncio
import asyncpg
import aiofiles
from zoneinfo import ZoneInfo

from db import init_db_pool, db_pool

# Create a blueprint
backup_blueprint = Blueprint('backup', __name__)

# Function to get or update the last backup timestamp
def get_last_backup_timestamp():
    timestamp_file = "/backups/last_backup_timestamp.txt"
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
    timestamp_file = "/backups/last_backup_timestamp.txt"
    with open(timestamp_file, 'w') as f:
        f.write(timestamp)

@backup_blueprint.route('/trigger_data_dump', methods=['POST'])
async def trigger_data_dump():
    try:
        # Backup directory
        backup_dir = "/backups"
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
            "-U", "pythonuser",
            "-d", "data",
            "-f", backup_file
        ], check=True, env=env)

        # Step 2: Zip the .sql file
        subprocess.run([
            "zip", "-j", zip_file, backup_file
        ], check=True)

        # (Optional) Step 3: Remove the raw .sql if you only want zip
        # os.remove(backup_file)

        return jsonify({"message": f"Data backup successful: {backup_file}"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@backup_blueprint.route('/trigger_data_data_only', methods=['POST'])
async def trigger_data_data_only():
    try:
        # Backup directory
        backup_dir = "/backups"
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
            "-U", "pythonuser",
            "-d", "data",
            "-f", backup_file
        ], check=True, env=env)

        # Step 2: Zip the .sql file
        subprocess.run([
            "zip", "-j", zip_file, backup_file
        ], check=True)

        # (Optional) Step 3: Remove the raw .sql if you only want zip
        # os.remove(backup_file)

        return jsonify({"message": f"Data backup successful: {backup_file}"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Main Quart app
app = Quart(__name__)

# Register the blueprint
app.register_blueprint(backup_blueprint)

 # Use Quart's async lifecycle hook (before_serving instead of before_first_request)
@app.before_serving
async def initialize_db():
    await init_db_pool()

@app.after_serving
async def shutdown():
    if db_pool is not None:
        await db_pool.close()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
