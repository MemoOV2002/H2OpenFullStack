"""
Shared packet processor for H2Open.
Called by both the HTTP ingest endpoint and the serial service.
Runs ML inference, writes to DB, broadcasts via WebSocket.
"""
import json
import logging
import joblib
import numpy as np
import pandas as pd
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Model paths ───────────────────────────────────────────────────────────────
BACKEND_DIR      = Path(__file__).resolve().parent.parent.parent
ECOLI_MODEL_PATH = BACKEND_DIR / "ml" / "ecoli_model_v2.joblib"
ECOLI_MAPIE_PATH = BACKEND_DIR / "ml" / "ecoli_mapie_v2.joblib"
ECOLI_META_PATH  = BACKEND_DIR / "ml" / "ecoli_meta_v2.joblib"
CYANO_MODEL_PATH = BACKEND_DIR / "ml" / "model" / "cyano_model.pkl"

# ── Constants ─────────────────────────────────────────────────────────────────
EPA_THRESHOLD   = 235.0
CHARLES_LAT     = 42.3601
CHARLES_LON     = -71.0589
RAINFALL_CACHE  = BACKEND_DIR / "ml" / "rainfall_cache.json"
CACHE_TTL_HOURS = 1
MM_TO_IN        = 1 / 25.4

# ── Lazy-loaded model singletons ──────────────────────────────────────────────
_ecoli_model = None
_ecoli_mapie = None
_ecoli_meta  = None
_cyano_model = None


def _load_models():
    global _ecoli_model, _ecoli_mapie, _ecoli_meta, _cyano_model
    if _ecoli_model is not None:
        return

    logger.info(f"Loading ML models from {BACKEND_DIR / 'ml'}...")
    try:
        _ecoli_model = joblib.load(ECOLI_MODEL_PATH)
        _ecoli_mapie = joblib.load(ECOLI_MAPIE_PATH)
        _ecoli_meta  = joblib.load(ECOLI_META_PATH)
        logger.info("E. coli models loaded.")
    except Exception as e:
        logger.error(f"Failed to load E. coli models: {e}")

    try:
        _cyano_model = joblib.load(CYANO_MODEL_PATH)
        logger.info("Cyano model loaded.")
    except Exception as e:
        logger.error(f"Failed to load cyano model: {e}")


def _fetch_rainfall() -> dict:
    if RAINFALL_CACHE.exists():
        try:
            cached = json.loads(RAINFALL_CACHE.read_text())
            fetched_at = datetime.fromisoformat(cached["fetched_at"])
            if datetime.utcnow() - fetched_at < timedelta(hours=CACHE_TTL_HOURS):
                return cached["data"]
        except Exception:
            pass

    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={CHARLES_LAT}&longitude={CHARLES_LON}"
        f"&daily=precipitation_sum&timezone=America%2FNew_York"
        f"&past_days=3&forecast_days=1"
    )
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            payload = json.loads(resp.read())
        precip    = payload["daily"]["precipitation_sum"]
        rain_day0 = float(precip[3]) * MM_TO_IN if precip[3] is not None else 0.0
        rain_lag1 = float(precip[2]) * MM_TO_IN if precip[2] is not None else 0.0
        rain_lag2 = float(precip[1]) * MM_TO_IN if precip[1] is not None else 0.0
        rain_3day = sum(p * MM_TO_IN for p in precip[1:4] if p is not None)
        data = {
            "rain_day0_in":  rain_day0,
            "rain_lag1_in":  rain_lag1,
            "rain_lag2_in":  rain_lag2,
            "rain_3day_cum": rain_3day,
        }
        RAINFALL_CACHE.write_text(json.dumps({
            "fetched_at": datetime.utcnow().isoformat(),
            "data": data
        }))
        logger.info(f"Rainfall fetched: {data}")
        return data
    except Exception as e:
        logger.warning(f"Open-Meteo failed ({e}); using zeros.")
        return {"rain_day0_in": 0.0, "rain_lag1_in": 0.0, "rain_lag2_in": 0.0, "rain_3day_cum": 0.0}


def _predict_ecoli(conductivity, temperature, turbidity, ph, rainfall):
    _load_models()
    if _ecoli_model is None or _ecoli_mapie is None:
        logger.warning("E. coli model unavailable; returning defaults.")
        return 0.0, 0.0, True

    now = datetime.utcnow()
    doy = now.timetuple().tm_yday

    X = pd.DataFrame([{
        "turbidity_ntu":  turbidity,
        "temperature_c":  temperature,
        "conductance_ms": conductivity,
        "ph":             ph,
        "do_mg_l":        np.nan,
        "rain_day0_in":   rainfall["rain_day0_in"],
        "rain_lag1_in":   rainfall["rain_lag1_in"],
        "rain_lag2_in":   rainfall["rain_lag2_in"],
        "rain_3day_cum":  rainfall["rain_3day_cum"],
        "month":          now.month,
        "doy_sin":        np.sin(2 * np.pi * doy / 365),
        "doy_cos":        np.cos(2 * np.pi * doy / 365),
        "station_id":     np.nan,
    }])

    try:
        point_log = _ecoli_model.predict(X)[0]
        point_cfu = float(np.expm1(point_log))
        _, intervals = _ecoli_mapie.predict_interval(X)
        upper_ci  = float(np.expm1(intervals[0, 1]))
        is_safe   = upper_ci <= EPA_THRESHOLD
        logger.info(f"E. coli point={point_cfu:.1f} upper_ci={upper_ci:.1f} safe={is_safe}")
        return round(point_cfu, 2), round(upper_ci, 2), is_safe
    except Exception as e:
        logger.error(f"E. coli inference error: {e}")
        return 0.0, 0.0, True


def _predict_cyano(conductivity, temperature, turbidity, ph):
    _load_models()
    if _cyano_model is None:
        return False, 0.0
    X = np.array([[conductivity, temperature, turbidity, ph]])
    try:
        bloom = bool(_cyano_model.predict(X)[0])
        prob  = float(_cyano_model.predict_proba(X)[0][1])
        return bloom, round(prob, 4)
    except Exception as e:
        logger.error(f"Cyano inference error: {e}")
        return False, 0.0


async def process_packet(
    *,
    conductivity: float,
    temperature: float,
    turbidity: float,
    ph: float,
    buoy_id: str = "BUOY_01",
    rssi: float = None,
    snr: float = None,
    db,
) -> dict:
    from app.models import SensorReading, BuoyStatus
    from app.routers.websocket import manager

    rainfall = _fetch_rainfall()
    ecoli_point, ecoli_upper_ci, is_safe_ecoli = _predict_ecoli(
        conductivity, temperature, turbidity, ph, rainfall
    )
    cyano_bloom, cyano_prob = _predict_cyano(conductivity, temperature, turbidity, ph)

    is_safe      = is_safe_ecoli and not cyano_bloom
    safety_level = "GREEN" if is_safe else "RED"
    now          = datetime.utcnow()

    try:
        db_reading = SensorReading(
            buoy_id=buoy_id,
            ecoli_cfu=ecoli_upper_ci,
            temperature=temperature,
            ph=ph,
            turbidity=turbidity,
            conductivity=conductivity,
            is_safe=is_safe,
        )
        db.add(db_reading)

        buoy_status = db.query(BuoyStatus).filter(BuoyStatus.buoy_id == buoy_id).first()
        if buoy_status:
            buoy_status.last_reading_time = now
            buoy_status.last_ecoli_cfu    = ecoli_upper_ci
            buoy_status.is_safe           = is_safe
            buoy_status.is_online         = True
            buoy_status.last_heartbeat    = now
        else:
            db.add(BuoyStatus(
                buoy_id=buoy_id,
                last_reading_time=now,
                last_ecoli_cfu=ecoli_upper_ci,
                is_safe=is_safe,
                is_online=True,
                last_heartbeat=now,
            ))

        db.commit()
        db.refresh(db_reading)
        reading_id = db_reading.id
    except Exception as e:
        logger.error(f"DB write failed: {e}")
        db.rollback()
        reading_id = None

    result = {
        "type":           "sensor_reading",
        "reading_id":     reading_id,
        "buoy_id":        buoy_id,
        "timestamp":      now.isoformat(),
        "conductivity":   conductivity,
        "temperature":    temperature,
        "turbidity":      turbidity,
        "ph":             ph,
        "ecoli_cfu":      ecoli_point,
        "ecoli_upper_ci": ecoli_upper_ci,
        "cyano_bloom":    cyano_bloom,
        "cyano_prob":     cyano_prob,
        "is_safe":        is_safe,
        "safety_level":   safety_level,
        "epa_threshold":  EPA_THRESHOLD,
        "rainfall":       rainfall,
        **({"rssi": rssi, "snr": snr} if rssi is not None else {}),
    }

    try:
        await manager.broadcast(result)
        logger.info(
            f"[{buoy_id}] ecoli_upper_ci={ecoli_upper_ci:.1f} | "
            f"cyano={'YES' if cyano_bloom else 'NO'} | safe={is_safe}"
        )
    except Exception as e:
        logger.error(f"WebSocket broadcast failed: {e}")

    return result