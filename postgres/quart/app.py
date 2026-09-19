from quart import Quart, Blueprint, jsonify, current_app
import os
import subprocess
from datetime import datetime
from datetime import timezone
import asyncio
import asyncpg
import aiofiles
from zoneinfo import ZoneInfo

from db import init_db_pool, init_db_pool_about, db_pool

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

@backup_blueprint.route('/trigger_about_data_only', methods=['POST'])
async def trigger_about_data_only():
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
        backup_file = f"{backup_dir}/about_data_only_{timestamp}.sql"
        zip_file = f"{backup_dir}/about_data_only_{timestamp}.zip"

        env = os.environ.copy()
        env['PGUSER'] = "pythonuser"

        subprocess.run([
            "pg_dump",
            "--data-only",  # Include data inserts only
            "-U", "pythonuser",
            "-d", "about",
            "-f", backup_file
        ], check=True, env=env)

        # Step 2: Zip the .sql file
        subprocess.run([
            "zip", "-j", zip_file, backup_file
        ], check=True)

        # (Optional) Step 3: Remove the raw .sql if you only want zip
        # os.remove(backup_file)

        return jsonify({"message": f"About backup successful: {backup_file}"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@backup_blueprint.route('/trigger_about_dump', methods=['POST'])
async def trigger_about_dump():
    try:
        # Backup directory
        backup_dir = "/backups"
        os.makedirs(backup_dir, exist_ok=True)

        # Define US timezone using zoneinfo
        #us_timezone = ZoneInfo("America/New_York")

        # Generate timestamped backup filename
        #current_time = datetime.now(us_timezone)
        current_time = datetime.now()
        timestamp = current_time.strftime("%Y%m%d_%H%M")
        backup_file = f"{backup_dir}/about_dump_{timestamp}.sql"
        zip_file = f"{backup_dir}/about_dump_{timestamp}.zip"
        
        env = os.environ.copy()
        env['PGUSER'] = "pythonuser"

        subprocess.run([
            "pg_dump",
            "-U", "pythonuser",
            "-d", "about",
            "-f", backup_file
        ], check=True, env=env)

        # Step 2: Zip the .sql file
        subprocess.run([
            "zip", "-j", zip_file, backup_file
        ], check=True)

        # (Optional) Step 3: Remove the raw .sql if you only want zip
        # os.remove(backup_file)

        return jsonify({"message": f"About backup successful: {backup_file}"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@backup_blueprint.route('/trigger_wiki_dump', methods=['POST'])
async def trigger_wiki_dump():
    try:
        # Backup directory
        backup_dir = "/backups"
        os.makedirs(backup_dir, exist_ok=True)

        # Define US timezone using zoneinfo
        # us_timezone = ZoneInfo("America/New_York")

        # Generate timestamped backup filename
        # current_time = datetime.now(us_timezone)
        current_time = datetime.now()
        timestamp = current_time.strftime("%Y%m%d_%H%M")
        backup_file = f"{backup_dir}/wiki_dump_{timestamp}.sql"
        zip_file = f"{backup_dir}/wiki_dump_{timestamp}.zip"

        env = os.environ.copy()
        env['PGUSER'] = "wikiuser"

        subprocess.run([
            "pg_dump",
            "-U", "wikiuser",
            "-d", "wiki",
            "-f", backup_file
        ], check=True, env=env)

        # Step 2: Zip the .sql file
        subprocess.run([
            "zip", "-j", zip_file, backup_file
        ], check=True)

        # (Optional) Step 3: Remove the raw .sql if you only want zip
        # os.remove(backup_file)

        return jsonify({"message": f"Wiki backup successful: {backup_file}"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@backup_blueprint.route('/trigger_incremental_backup', methods=['POST'])
async def trigger_incremental_backup():
    try:
        db_pool = await init_db_pool()
        # Ensure db_pool is initialized
        if db_pool is None:
            return jsonify({"error": "Database connection pool not initialized"}), 500

        # Backup directory
        backup_dir = "/backups"
        os.makedirs(backup_dir, exist_ok=True)

        # Define US timezone using zoneinfo
        # us_timezone = ZoneInfo("America/New_York")

        # Generate timestamped backup filename
        #current_time = datetime.now(us_timezone)
        current_time = datetime.now()
        timestamp = current_time.strftime("%Y%m%d_%H%M")
        
        node_backup_file = f"{backup_dir}/node_incremental_backup_{timestamp}.csv"
        relationship_backup_file = f"{backup_dir}/relationship_incremental_backup_{timestamp}.csv"

        # Get the last backup timestamp
        last_backup_timestamp = get_last_backup_timestamp()
        current_timestamp = datetime.now(timezone.utc)  # Current timestamp in UTC

        if not last_backup_timestamp:
            last_backup_timestamp = datetime(1970, 1, 1, tzinfo=timezone.utc)  # Default to Unix epoch in UTC

        async with db_pool.acquire() as conn:
            # Export modified rows from the `node` table
            node_query = f"""
                COPY (
                    SELECT * FROM node
                    WHERE updated > '{last_backup_timestamp.isoformat()}'
                ) TO '{node_backup_file}' WITH CSV HEADER
            """
            await conn.execute(node_query)

            # Export modified rows from the `relationship` table
            relationship_query = f"""
                COPY (
                    SELECT * FROM relationship
                    WHERE updated > '{last_backup_timestamp.isoformat()}'
                ) TO '{relationship_backup_file}' WITH CSV HEADER
            """
            await conn.execute(relationship_query)

        # Update the last backup timestamp
        update_last_backup_timestamp(current_timestamp.isoformat())  # Save as ISO 8601 string

        return jsonify({
            "message": "Incremental data backup successful",
            "node_backup_file": node_backup_file,
            "relationship_backup_file": relationship_backup_file
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@backup_blueprint.route('/restore_all_incremental_backups', methods=['POST'])
async def restore_all_incremental_backups():
    try:
        db_pool = await init_db_pool()
        # Ensure db_pool is initialized
        if db_pool is None:
            return jsonify({"error": "Database connection pool not initialized"}), 500

        # Backup directory
        backup_dir = "/backups"
        if not os.path.exists(backup_dir):
            return jsonify({"error": f"Backup directory does not exist: {backup_dir}"}), 400

        # Get a sorted list of all incremental backup files
        node_files = sorted(
            [
                os.path.join(backup_dir, file)
                for file in os.listdir(backup_dir)
                if file.endswith(".csv") and "node" in file and "incremental" in file
            ]
        )
        relationship_files = sorted(
            [
                os.path.join(backup_dir, file)
                for file in os.listdir(backup_dir)
                if file.endswith(".csv") and "relationship" in file and "incremental" in file
            ]
        )

        async with db_pool.acquire() as conn:
            # Restore data for the `node` table
            for node_file in node_files:
                node_query = f"""
                    COPY node FROM '{node_file}' WITH CSV HEADER
                """
                await conn.execute(node_query)

            # Restore data for the `relationship` table
            for relationship_file in relationship_files:
                relationship_query = f"""
                    COPY relationship FROM '{relationship_file}' WITH CSV HEADER
                """
                await conn.execute(relationship_query)

        return jsonify({"message": "All incremental data backups restored successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


async def process_incremental_backup(conn, file_path, table_name):
    temp_table = f"temp_{table_name}"
    try:
        # Create a temporary table
        await conn.execute(f"""
            CREATE TEMP TABLE {temp_table} (LIKE {table_name} INCLUDING ALL)
        """)

        # Load CSV data into the temporary table
        await conn.execute(f"""
            COPY {temp_table} FROM '{file_path}' WITH CSV HEADER
        """)

        # Merge data into the main table
        if table_name == 'node':
            await conn.execute(f"""
                INSERT INTO node (id, properties, type, created, updated, archived)
                SELECT id, properties, type, created, updated, archived
                FROM {temp_table}
                ON CONFLICT (id) DO UPDATE
                SET
                    properties = EXCLUDED.properties,
                    type = EXCLUDED.type,
                    updated = EXCLUDED.updated,
                    archived = CASE
                        WHEN node.archived IS NULL OR node.archived > EXCLUDED.archived THEN EXCLUDED.archived
                        ELSE node.archived
                    END
                WHERE node.updated < EXCLUDED.updated;
            """)
        elif table_name == 'relationship':
            await conn.execute(f"""
                INSERT INTO relationship (id, properties, label, created, updated, archived)
                SELECT id, properties, label, created, updated, archived
                FROM {temp_table}
                ON CONFLICT (id) DO UPDATE
                SET
                    properties = EXCLUDED.properties,
                    label = EXCLUDED.label,
                    updated = EXCLUDED.updated,
                    archived = CASE
                        WHEN relationship.archived IS NULL OR relationship.archived > EXCLUDED.archived THEN EXCLUDED.archived
                        ELSE relationship.archived
                    END
                WHERE relationship.updated < EXCLUDED.updated;
            """)

        # Drop the temporary table
        await conn.execute(f"DROP TABLE {temp_table}")

    except Exception as e:
        print(f"Error processing {file_path} for table {table_name}: {e}")
        raise


@backup_blueprint.route('/restore_all_incremental_backups_merge', methods=['POST'])
async def restore_all_incremental_backups_merge():
    try:
        db_pool = await init_db_pool()
        if db_pool is None:
            return jsonify({"error": "Database connection pool not initialized"}), 500

        # Backup directory
        backup_dir = "/backups"
        if not os.path.exists(backup_dir):
            return jsonify({"error": f"Backup directory does not exist: {backup_dir}"}), 400

        # Get a sorted list of all incremental backup files
        node_files = sorted(
            [
                os.path.join(backup_dir, file)
                for file in os.listdir(backup_dir)
                if file.endswith(".csv") and "node" in file and "incremental" in file
            ]
        )
        relationship_files = sorted(
            [
                os.path.join(backup_dir, file)
                for file in os.listdir(backup_dir)
                if file.endswith(".csv") and "relationship" in file and "incremental" in file
            ]
        )

        async with db_pool.acquire() as conn:
            # Process node files
            for node_file in node_files:
                await process_incremental_backup(conn, node_file, 'node')

            # Process relationship files
            for relationship_file in relationship_files:
                await process_incremental_backup(conn, relationship_file, 'relationship')

        return jsonify({"message": "All incremental data backups restored successfully"}), 200

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
    await init_db_pool_about()

@app.after_serving
async def shutdown():
    if db_pool is not None:
        await db_pool.close()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
