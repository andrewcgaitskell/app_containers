# db.py
import asyncpg
import os
from dotenv import load_dotenv

db_pool = None
db_pool_about = None

# Asynchronously initialize the database connection pool
async def init_db_pool():
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    GRANDPARENT_DIR = os.path.abspath(os.path.join(BASE_DIR, os.pardir, os.pardir))
    STATUS = "prod"
    # Load environment variables from .env file
    #load_dotenv(os.path.join(GRANDPARENT_DIR, ".env"))
    print("postgres base_dir >>> ", BASE_DIR)
    load_dotenv(os.path.join(BASE_DIR, ".env"))

    # Retrieve environment variables
    ENV_POSTGRES_USER = os.environ.get("ENV_POSTGRES_USER")
    ENV_POSTGRES_PASSWORD = os.environ.get("ENV_POSTGRES_PASSWORD")
    ENV_POSTGRES_DB = os.environ.get("ENV_POSTGRES_DB")
    POSTGRES_HOST = os.environ.get("ENV_POSTGRES_DB_HOST")

    print("user:", ENV_POSTGRES_USER, "password:" , ENV_POSTGRES_PASSWORD, "database:" , ENV_POSTGRES_DB)

    # Check if required environment variables are set
    if not all([ENV_POSTGRES_USER, ENV_POSTGRES_PASSWORD, ENV_POSTGRES_DB]):
        raise ValueError("Missing required Postgres environment variables")

    global db_pool
    
    # Initialize and return the connection pool
    if db_pool is None:
        print("Initializing the db_pool...")
        db_pool =  await asyncpg.create_pool(
        user=ENV_POSTGRES_USER,
        password=ENV_POSTGRES_PASSWORD,
        database=ENV_POSTGRES_DB,
        host=POSTGRES_HOST,
        min_size=5,  # Optional: set minimum number of connections in the pool
        max_size=20  # Optional: set maximum number of connections in the pool
    )
    else:
        print("db_pool already initialized")

    return db_pool

# Asynchronously initialize the database connection pool
# about is the security database

async def init_db_pool_about():
    
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    GRANDPARENT_DIR = os.path.abspath(os.path.join(BASE_DIR, os.pardir, os.pardir))
    STATUS = "dev"
    # Load environment variables from .env file
    load_dotenv(os.path.join(GRANDPARENT_DIR, ".env"))

    # Retrieve environment variables
    ENV_POSTGRES_USER = 'aboutuser'
    ENV_POSTGRES_PASSWORD = os.environ.get("ENV_ABOUT_PASSWORD")
    ENV_POSTGRES_DB = 'about'
    POSTGRES_HOST = os.environ.get("ENV_POSTGRES_DB_HOST")

    # Check if required environment variables are set
    if not all([ENV_POSTGRES_PASSWORD]):
        raise ValueError("Missing required Postgres environment variables - about")

    global db_pool_about
    
    # Initialize and return the connection pool
    if db_pool_about is None:
        print("Initializing the db_pool...")
        db_pool_about =  await asyncpg.create_pool(
                user='aboutuser',
                password=ENV_POSTGRES_PASSWORD,
                database='about',
                host=POSTGRES_HOST,
                min_size=5,  # Optional: set minimum number of connections in the pool
                max_size=20  # Optional: set maximum number of connections in the pool
            )
    else:
        print("db_pool_about already initialized")

    return db_pool_about
  
