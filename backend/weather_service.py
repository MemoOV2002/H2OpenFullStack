"""
H2Open — Weather Service
=========================
Fetches recent rainfall from the Open-Meteo archive API for Logan Airport
(lat=42.3656, lon=-71.0096) and returns the lag features the ML model needs.

Results are cached in memory for CACHE_TTL_MINUTES to avoid hammering the API
on every buoy packet.  Thread-safe via a module-level lock.

Rainfall features returned (all in inches, matching MWRA training data):
    rain_day0_in:   today's total precipitation
    rain_lag1_in:   yesterday's total precipitation
    rain_lag2_in:   2 days ago total precipitation
    rain_3day_cum:  sum of all three (3-day cumulative)
"""

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Logan Airport coordinates (matching MWRA Logan rainfall data)
LAT = 42.3656
LON = -71.0096

CACHE_TTL_MINUTES = 30  # refresh at most twice per hour

_cache: dict = {}
_cache_ts: Optional[datetime] = None
_lock = threading.Lock()


def get_rainfall_lags() -> dict:
    """
    Returns rainfall lag features dict. Uses cached value if fresh enough.
    Falls back to zeros on any API error — model handles missing features via imputation.
    """
    global _cache, _cache_ts

    with _lock:
        now = datetime.now(tz=timezone.utc)
        if _cache_ts and (now - _cache_ts).total_seconds() < CACHE_TTL_MINUTES * 60:
            return _cache

        try:
            result = _fetch_from_openmeteo()
            _cache    = result
            _cache_ts = now
            logger.info("Rainfall updated: %s", result)
            return result
        except Exception as e:
            logger.warning("Open-Meteo fetch failed: %s — returning zeros", e)
            return {"rain_day0_in": 0.0, "rain_lag1_in": 0.0,
                    "rain_lag2_in": 0.0, "rain_3day_cum": 0.0}


def _fetch_from_openmeteo() -> dict:
    """Fetches last 3 days of daily precipitation from Open-Meteo archive."""
    today     = datetime.now(tz=timezone.utc).date()
    start     = today - timedelta(days=3)   # extra day buffer

    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude":        LAT,
        "longitude":       LON,
        "start_date":      start.isoformat(),
        "end_date":        today.isoformat(),
        "daily":           "precipitation_sum",
        "timezone":        "America/New_York",
        "precipitation_unit": "inch",
    }

    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    dates  = data["daily"]["time"]                   # list of "YYYY-MM-DD"
    precip = data["daily"]["precipitation_sum"]      # list of floats or None

    # Build a date → inches map; replace None with 0
    rain_map = {d: (p or 0.0) for d, p in zip(dates, precip)}

    today_str = today.isoformat()
    lag1_str  = (today - timedelta(days=1)).isoformat()
    lag2_str  = (today - timedelta(days=2)).isoformat()

    r0 = rain_map.get(today_str, 0.0)
    r1 = rain_map.get(lag1_str,  0.0)
    r2 = rain_map.get(lag2_str,  0.0)

    return {
        "rain_day0_in":  round(r0, 3),
        "rain_lag1_in":  round(r1, 3),
        "rain_lag2_in":  round(r2, 3),
        "rain_3day_cum": round(r0 + r1 + r2, 3),
    }