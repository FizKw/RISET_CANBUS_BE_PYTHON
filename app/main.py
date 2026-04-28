import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import connect_db, disconnect_db, get_vehicle_collection
from app.services.buffer_service import flush_loop
from app.services.mqtt_service import start_mqtt, stop_mqtt
from app.api.routes.telemetry import router as telemetry_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    await connect_db()

    # Start background buffer flush task
    flush_task = asyncio.create_task(flush_loop(get_vehicle_collection))

    # Start MQTT in a daemon thread, passing the current event loop
    loop = asyncio.get_event_loop()
    start_mqtt(loop)

    logger.info("Backend running on port 4000")
    yield

    # --- Shutdown ---
    flush_task.cancel()
    try:
        await flush_task
    except asyncio.CancelledError:
        pass

    stop_mqtt()
    await disconnect_db()


app = FastAPI(title="Vehicle Telemetry API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.CORS_ORIGIN],
    allow_credentials=True,
    allow_methods=["GET", "HEAD", "PUT", "PATCH", "POST", "DELETE"],
    allow_headers=["*"],
)

app.include_router(telemetry_router)