"""
predict() — callable by the FastAPI backend to estimate E. coli CFU/100mL.
predict_cyano() — predicts cyanobacteria bloom risk (binary: True = bloom likely).

The models must be trained first:
    python -m ml.train
    python -m ml.train_cyano
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent / "model"
MODEL_PATH = MODEL_DIR / "model.joblib"
META_PATH = MODEL_DIR / "meta.json"
ENCODER_PATH = MODEL_DIR / "station_encoder.joblib"
CYANO_MODEL_PATH = MODEL_DIR / "cyano_model.pkl"

EPA_THRESHOLD = 235.0  # CFU/100mL

_pipeline = None
_meta = None
_station_encoder = None
_cyano_pipeline = None


def _load():
    global _pipeline, _meta, _station_encoder
    if _pipeline is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Model not found at {MODEL_PATH}. Run `python -m ml.train` first."
            )
        _pipeline = joblib.load(MODEL_PATH)
        _meta = json.loads(META_PATH.read_text())
        _station_encoder = joblib.load(ENCODER_PATH)
        log.info("E. coli ML model loaded.")


def _load_cyano():
    global _cyano_pipeline
    if _cyano_pipeline is None:
        if not CYANO_MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Cyano model not found at {CYANO_MODEL_PATH}. Run `python -m ml.train_cyano` first."
            )
        _cyano_pipeline = joblib.load(CYANO_MODEL_PATH)
        log.info("Cyano ML model loaded.")


def predict(
    temperature: Optional[float] = None,
    dissolved_oxygen: Optional[float] = None,
    do_pct_saturation: Optional[float] = None,
    ph: Optional[float] = None,
    turbidity: Optional[float] = None,
    salinity: Optional[float] = None,
    conductance: Optional[float] = None,
    rainfall_1day: float = 0.0,
    rainfall_2day: float = 0.0,
    rainfall_3day: float = 0.0,
    station_id: Optional[str] = None,
    sample_datetime: Optional[datetime] = None,
) -> dict:
    """
    Predict E. coli concentration from physical water quality measurements.

    Returns:
        {
            "predicted_ecoli_cfu": float,   # CFU/100mL
            "is_safe": bool,                # True if < 235 CFU/100mL (EPA standard)
            "model_mae_cfu": float,         # Model's mean absolute error on test set
        }
    """
    _load()

    dt = sample_datetime or datetime.utcnow()

    # Encode station ID
    known = set(_station_encoder.classes_)
    sid = str(station_id) if station_id else None
    station_encoded = (
        int(_station_encoder.transform([sid])[0]) if sid and sid in known else -1
    )

    row = {
        "Temperature (C)": temperature,
        "Dissolved Oxygen (mg/L)": dissolved_oxygen,
        "DO Pct Saturation (%)": do_pct_saturation,
        "pH": ph,
        "Turbidity (NTU)": turbidity,
        "Salinity (PSU)": salinity,
        "Specific Conductance (mS/cm)": conductance,
        "rainfall_1day": rainfall_1day,
        "rainfall_2day": rainfall_2day,
        "rainfall_3day": rainfall_3day,
        "month": dt.month,
        "day_of_year": dt.timetuple().tm_yday,
        "station_encoded": station_encoded,
    }

    # Keep only features the model was trained on, in the right order
    features = _meta["features"]
    X = pd.DataFrame([[row.get(f) for f in features]], columns=features)

    log_pred = _pipeline.predict(X)[0]
    predicted_cfu = float(np.expm1(log_pred))
    predicted_cfu = max(0.0, predicted_cfu)

    return {
        "predicted_ecoli_cfu": round(predicted_cfu, 1),
        "is_safe": predicted_cfu < EPA_THRESHOLD,
        "model_mae_cfu": _meta.get("test_mae_cfu"),
    }


def predict_cyano(
    temperature: Optional[float] = None,
    conductivity: Optional[float] = None,
    ph: Optional[float] = None,
    turbidity: Optional[float] = None,
) -> dict:
    """
    Predict cyanobacteria bloom risk from buoy sensor readings.

    Features must match the buoy's output units:
        temperature   °C
        conductivity  µS/cm
        ph            standard units
        turbidity     NTU

    Returns:
        {
            "cyano_bloom": bool,   # True = bloom likely (>= 70,000 cells/mL)
        }
    """
    _load_cyano()

    X = pd.DataFrame([[temperature, conductivity, ph, turbidity]],
                     columns=["temperature", "conductivity", "ph", "turbidity"])

    bloom = bool(_cyano_pipeline.predict(X)[0])

    return {"cyano_bloom": bloom}


def model_loaded() -> bool:
    """Return True if the E. coli model file exists and has been loaded."""
    return MODEL_PATH.exists()


def cyano_model_loaded() -> bool:
    """Return True if the cyano model file exists."""
    return CYANO_MODEL_PATH.exists()