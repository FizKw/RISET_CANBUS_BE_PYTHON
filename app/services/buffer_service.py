import asyncio
import logging
import threading
from typing import List

logger = logging.getLogger(__name__)

# Shared buffer — written by Paho thread, drained by asyncio flush task.
_buffer: List[dict] = []
_lock = threading.Lock()


def add_to_buffer(document: dict) -> None:
    """Thread-safe append. Called from the Paho MQTT callback thread."""
    with _lock:
        _buffer.append(document)


async def flush_loop(get_collection) -> None:
    """
    Background asyncio task.
    Drains the buffer every 1 second and batch-inserts into MongoDB.
    Uses insert_many() for efficiency — supports 10+ messages/second easily.
    """
    while True:
        await asyncio.sleep(1.0)

        with _lock:
            if not _buffer:
                continue
            batch = _buffer.copy()
            _buffer.clear()

        collection = get_collection()
        if collection is None:
            logger.warning("Collection not ready, re-queuing batch")
            with _lock:
                _buffer[:0] = batch  # prepend back
            continue

        try:
            result = await collection.insert_many(batch, ordered=False)
            logger.info("Inserted %d records", len(result.inserted_ids))
        except Exception as exc:
            logger.error("Batch insert failed: %s", exc)