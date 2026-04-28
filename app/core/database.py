import logging
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import CollectionInvalid
from app.core.config import settings

logger = logging.getLogger(__name__)

client: AsyncIOMotorClient = None
db = None
vehicle_collection = None


async def connect_db():
    global client, db, vehicle_collection

    client = AsyncIOMotorClient(settings.MONGO_URI)
    db = client[settings.MONGO_DB]

    await _ensure_timeseries_collection(db)

    vehicle_collection = db["Vehicle"]
    logger.info("MongoDB connected")


async def _ensure_timeseries_collection(database):
    """Create time-series collection if it does not exist yet."""
    existing = await database.list_collection_names()
    if "Vehicle" not in existing:
        try:
            await database.create_collection(
                "Vehicle",
                timeseries={
                    "timeField": "timestamp",
                    "metaField": "vehicleId",
                    "granularity": "seconds",
                },
            )
            logger.info("Time-series collection 'Vehicle' created")
        except CollectionInvalid:
            # Race condition: another process created it first
            logger.warning("Collection 'Vehicle' already exists, skipping creation")
    else:
        logger.info("Collection 'Vehicle' already exists")


async def disconnect_db():
    global client
    if client:
        client.close()
        logger.info("MongoDB disconnected")


def get_vehicle_collection():
    return vehicle_collection