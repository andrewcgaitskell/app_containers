# db.py
import asyncpg
import os

db_pool = None

# Asynchronously initialize the main database connection pool
async def init_db_pool():
    # Compose injects these directly into the container's environment,
    # so no .env file needs to be loaded here.
    POSTGRES_USER = os.environ.get("POSTGRES_USER")
    POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD")
    POSTGRES_DB = os.environ.get("POSTGRES_DB")
    POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")

    print("user:", POSTGRES_USER, "database:", POSTGRES_DB, "host:", POSTGRES_HOST)

    if not all([POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB]):
        raise ValueError("Missing required Postgres environment variables")

    global db_pool

    if db_pool is None:
        print("Initializing the db_pool...")
        db_pool = await asyncpg.create_pool(
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database=POSTGRES_DB,
            host=POSTGRES_HOST,
            min_size=5,   # Optional: minimum number of connections in the pool
            max_size=20,  # Optional: maximum number of connections in the pool
        )
    else:
        print("db_pool already initialized")

    return db_pool
