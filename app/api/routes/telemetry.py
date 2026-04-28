import logging
from typing import Optional, Literal
from datetime import datetime

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse

from app.core.database import get_vehicle_collection
from app.utils.time_utils import get_range_start, get_aggregation_interval_ms

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

ALLOWED_METRICS = {
    "speed", "rpm", "throttle", "gear",
    "brake", "engineCoolantTemp", "airIntakeTemp", "odoMeter",
}


def _serialize(doc: dict) -> dict:
    """Convert MongoDB document to JSON-safe dict (handles datetime and ObjectId)."""
    result = {}
    for k, v in doc.items():
        if k == "_id":
            continue
        if isinstance(v, datetime):
            result[k] = v.isoformat()
        else:
            result[k] = v
    return result


# ---------------------------------------------------------------------------
# GET /api/test
# ---------------------------------------------------------------------------

@router.get("/test")
async def test():
    return "test"


# ---------------------------------------------------------------------------
# GET /api/telemetry/latest
# ---------------------------------------------------------------------------

@router.get("/telemetry/latest")
async def get_latest():
    collection = get_vehicle_collection()
    cursor = collection.find({}, {"_id": 0}).sort("timestamp", -1).limit(10)
    docs = await cursor.to_list(length=10)
    return [_serialize(d) for d in docs]


# ---------------------------------------------------------------------------
# GET /api/telemetry/odometer
# ---------------------------------------------------------------------------

@router.get("/telemetry/odometer")
async def get_odometer(
    vehicleId: str = Query(...),
    range: str = Query(default="30d"),
):
    collection  = get_vehicle_collection()
    range_start = get_range_start(range)
    bucket_ms   = get_aggregation_interval_ms(range)

    pipeline = [
        # Stage 1: filter by vehicleId and optional time range
        {
            "$match": {
                "vehicleId": vehicleId,
                **({"timestamp": {"$gte": range_start}} if range_start else {}),
            }
        },
        # Stage 2: calculate time bucket per document
        {
            "$project": {
                "odoMeter": 1,
                "bucket": {
                    "$toDate": {
                        "$multiply": [
                            {
                                "$floor": {
                                    "$divide": [
                                        {"$toLong": "$timestamp"},
                                        bucket_ms,
                                    ]
                                }
                            },
                            bucket_ms,
                        ]
                    }
                },
            }
        },
        # Stage 3: group by bucket, take max odoMeter (cumulative data)
        {
            "$group": {
                "_id": "$bucket",
                "odo": {"$max": "$odoMeter"},
            }
        },
        {"$sort": {"_id": 1}},
        # Stage 4: final projection matching Node.js response shape
        {
            "$project": {
                "_id": 0,
                "bucket": "$_id",
                "odo": 1,
            }
        },
    ]

    cursor = collection.aggregate(pipeline)
    aggregated = await cursor.to_list(length=None)

    # Serialize datetime bucket fields
    serialized = [_serialize(d) for d in aggregated]

    return JSONResponse(
        content={
            "vehicleId":       vehicleId,
            "range":           range,
            "intervalMinutes": bucket_ms / (60 * 1000),
            "count":           len(serialized),
            "data":            serialized,
        }
    )


# ---------------------------------------------------------------------------
# GET /api/telemetry/history
# ---------------------------------------------------------------------------

@router.get("/telemetry/history")
async def get_history(
    vehicleId: str = Query(...),
    metric: str   = Query(...),
    range: str    = Query(default="24h"),
):
    if metric not in ALLOWED_METRICS:
        raise HTTPException(status_code=400, detail="Invalid or missing metric")

    collection  = get_vehicle_collection()
    range_start = get_range_start(range)

    query: dict = {"vehicleId": vehicleId}
    if range_start:
        query["timestamp"] = {"$gte": range_start}

    projection = {"_id": 0, "timestamp": 1, metric: 1}
    cursor = collection.find(query, projection).sort("timestamp", 1)
    docs = await cursor.to_list(length=None)

    serialized = [_serialize(d) for d in docs]

    return JSONResponse(
        content={
            "vehicleId": vehicleId,
            "metric":    metric,
            "range":     range,
            "count":     len(serialized),
            "data":      serialized,
        }
    )