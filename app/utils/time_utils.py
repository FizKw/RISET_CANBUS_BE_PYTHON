from datetime import datetime, timezone
from typing import Optional


def get_range_start(range_str: str) -> Optional[datetime]:
    """
    Returns a timezone-aware datetime representing the start of the requested range.
    Returns None for 'all' (no time filter).
    Behavior is identical to the Node.js getRangeStart().
    """
    now = datetime.now(timezone.utc)
    ms = {
        "1h":   60 * 60 * 1000,
        "24h":  24 * 60 * 60 * 1000,
        "7d":   7 * 24 * 60 * 60 * 1000,
        "30d":  30 * 24 * 60 * 60 * 1000,
        "365d": 365 * 24 * 60 * 60 * 1000,
    }

    if range_str in ms:
        return datetime.fromtimestamp(
            (now.timestamp() * 1000 - ms[range_str]) / 1000,
            tz=timezone.utc,
        )

    if range_str == "ytd":
        return datetime(now.year, 1, 1, tzinfo=timezone.utc)

    # "all" or unknown
    return None


def get_aggregation_interval_ms(range_str: str) -> int:
    """
    Returns bucket size in milliseconds for aggregation.
    All cases return 1 minute (60000 ms), matching the Node.js getAggregationIntervalMs().
    """
    return 1 * 60 * 1000  # 60_000 ms — matches original behavior for every range