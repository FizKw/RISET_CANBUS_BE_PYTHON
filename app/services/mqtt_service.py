import asyncio
import json
import logging
import threading
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from app.core.config import settings
from app.schemas.vehicle import VehiclePayload
from app.services.buffer_service import add_to_buffer

logger = logging.getLogger(__name__)

# Topics
TOPIC_VEHICLE  = "esp32mqtt/vehicle"
TOPIC_BE_REQ   = "esp32mqtt/handshake/be/request"
TOPIC_BE_RES   = "esp32mqtt/handshake/be/response"
TOPIC_ODO_REQ  = "esp32mqtt/odo/sync/request"
TOPIC_ODO_RES  = "esp32mqtt/odo/sync/response"

# Holds a reference to the running asyncio event loop so Paho callbacks
# can schedule coroutines safely from their worker thread.
_loop: asyncio.AbstractEventLoop = None
_client: mqtt.Client = None


def _on_connect(client: mqtt.Client, userdata, flags, rc):
    if rc == 0:
        logger.info("MQTT connected (Backend)")
        client.subscribe(TOPIC_VEHICLE)
        client.subscribe(TOPIC_BE_REQ)
        client.subscribe(TOPIC_ODO_REQ)
    else:
        logger.error("MQTT connection failed, rc=%d", rc)


def _on_message(client: mqtt.Client, userdata, msg):
    topic   = msg.topic
    payload = msg.payload.decode("utf-8", errors="replace")

    # --- Odometer sync ---
    if topic == TOPIC_ODO_REQ:
        asyncio.run_coroutine_threadsafe(_handle_odo_sync(client), _loop)
        return

    # --- Handshake ---
    if topic == TOPIC_BE_REQ:
        logger.info("Handshake request from ESP: %s", payload)
        try:
            data = json.loads(payload)
            if data.get("status") == "ping":
                client.publish(TOPIC_BE_RES, json.dumps({"status": "ack"}))
                logger.info("Sent ACK to ESP")
        except json.JSONDecodeError as exc:
            logger.error("Invalid handshake payload: %s", exc)
        return

    # --- Telemetry ingestion ---
    if topic == TOPIC_VEHICLE:
        try:
            raw = json.loads(payload)
            vehicle = VehiclePayload(**raw)  # Pydantic validation
            doc = vehicle.model_dump()
            doc["timestamp"] = datetime.now(timezone.utc)
            add_to_buffer(doc)
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning("Invalid telemetry payload: %s", exc)


async def _handle_odo_sync(client: mqtt.Client):
    """Fetch latest odoMeter from MongoDB and publish back to ESP32."""
    from app.core.database import get_vehicle_collection

    collection = get_vehicle_collection()
    total_odo = 0.0

    if collection is not None:
        try:
            last = await collection.find_one(
                {}, sort=[("timestamp", -1)], projection={"odoMeter": 1}
            )
            if last:
                total_odo = last.get("odoMeter", 0.0)
        except Exception as exc:
            logger.error("Odo sync DB query failed: %s", exc)

    client.publish(TOPIC_ODO_RES, json.dumps({"totalOdoKm": total_odo}))
    logger.info("Sent odo sync: %s", total_odo)


def start_mqtt(loop: asyncio.AbstractEventLoop) -> None:
    """
    Initialize and start the Paho MQTT client in a background daemon thread.
    Must be called after the asyncio event loop is running.
    """
    global _loop, _client
    _loop = loop

    _client = mqtt.Client(transport="websockets")
    _client.username_pw_set(settings.MQTT_USER, settings.MQTT_PASS)
    
    _client.ws_set_options(path="/mqtt")
    _client.tls_set()

    _client.on_connect = _on_connect
    _client.on_message = _on_message

    _client.connect(settings.MQTT_HOST, settings.MQTT_PORT, keepalive=60)

    thread = threading.Thread(target=_client.loop_forever, daemon=True)
    thread.start()
    logger.info("MQTT client thread started")


def stop_mqtt() -> None:
    if _client:
        _client.disconnect()
        logger.info("MQTT client disconnected")