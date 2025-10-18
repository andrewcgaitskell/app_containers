import os
import asyncio
import json
import logging
import asyncpg
from quart import Quart, jsonify
from aiomqtt import Client

# Setup logging
logging.basicConfig(
    level=logging.INFO,  # Or DEBUG for more verbosity
    format="%(asctime)s [%(levelname)s] %(message)s"
)

app = Quart(__name__)

# DB Connection
DB_HOST = os.environ.get("POSTGRES_HOST", "postgres")
DB_USER = os.environ.get("POSTGRES_USER", "mqttuser")
DB_PASS = os.environ.get("POSTGRES_PASSWORD", "mqttpassword")
DB_NAME = os.environ.get("POSTGRES_DB", "mqttdb")

# MQTT Config
MQTT_BROKER = os.environ.get("MQTT_BROKER", "mosquitto")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))
MQTT_TOPIC = os.environ.get("MQTT_TOPIC", "#")

async def init_db():
    logging.info("Initializing database...")
    try:
        conn = await asyncpg.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME
        )
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS mqtt_messages (
            id SERIAL PRIMARY KEY,
            topic TEXT NOT NULL,
            qos SMALLINT,
            retain BOOLEAN,
            payload JSONB,
            received_at TIMESTAMPTZ DEFAULT NOW()
        );
        """)
        await conn.close()
        logging.info("Database initialized.")
    except Exception as e:
        logging.error(f"Error initializing database: {e}")

async def write_message(topic, qos, retain, payload):
    logging.info(f"Writing message to DB: topic={topic}, qos={qos}, retain={retain}, payload={payload}")
    try:
        conn = await asyncpg.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME
        )
        await conn.execute("""
            INSERT INTO mqtt_messages (topic, qos, retain, payload)
            VALUES ($1, $2, $3, $4)
        """, topic, qos, retain, json.dumps(payload))
        await conn.close()
        logging.info("Message written to database.")
    except Exception as e:
        logging.error(f"Error writing message to DB: {e}")

async def mqtt_listener():
    logging.info(f"Connecting to MQTT broker {MQTT_BROKER}:{MQTT_PORT}...")
    async with Client(MQTT_BROKER, port=MQTT_PORT) as client:
        logging.info(f"Connected to MQTT broker. Subscribing to topic '{MQTT_TOPIC}'...")
        await client.subscribe(MQTT_TOPIC)
        logging.info("Subscribed, waiting for messages...")
        async for message in client.messages:
            logging.info(f"Received message on topic {message.topic}")
            try:
                payload = json.loads(message.payload.decode())
                logging.debug(f"Decoded JSON payload: {payload}")
            except Exception:
                payload = {"raw": message.payload.decode(errors="replace")}
                logging.warning(f"Failed to decode JSON; storing raw payload.")
            await write_message(
                topic=str(message.topic),        # <-- Fix here!
                qos=message.qos,
                retain=getattr(message, "retain", None),
                payload=payload
            )

@app.before_serving
async def startup():
    await init_db()
    app.mqtt_task = asyncio.create_task(mqtt_listener())
    logging.info("MQTT listener started.")

@app.after_serving
async def cleanup():
    app.mqtt_task.cancel()
    try:
        await app.mqtt_task
    except asyncio.CancelledError:
        logging.info("MQTT listener cancelled.")

@app.route("/")
async def index():
    return jsonify({"status": "MQTT listener running"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
