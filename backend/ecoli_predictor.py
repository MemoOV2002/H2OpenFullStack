"""
H2Open — E. coli Inference Module
===================================
Loads the trained LightGBM + MAPIE conformal models and produces:
  - point_estimate_cfu:  median predicted E. coli (CFU/100mL)
  - lower_ci_cfu:        lower bound of conformal interval
  - upper_ci_cfu:        upper bound of conformal interval
  - is_unsafe:           True if upper_ci_cfu > tuned inference threshold (loaded from threshold.json)
  - uncertainty:         half-width of the interval (upper - lower) / 2
  - parameter_warnings:  list of advisory flags for temp, turbidity, pH, conductivity

The threshold comparison is intentionally done HERE, outside the model.
The model only predicts CFU values. is_unsafe is a post-hoc decision.

Usage in serial_service.py:
    from ecoli_predictor import EcoliPredictor
    predictor = EcoliPredictor()
    result = predictor.predict(
        turbidity_ntu=12.4,
        temperature_c=18.2,
        conductance_ms=0.45,
        ph=7.3,
        rain_3day_cum=0.85,    # from weather API (3-day cumulative, inches)
        rain_lag1_in=0.20,     # previous day rainfall only
        rain_lag2_in=0.10,     # 2 days ago rainfall only
        rain_day0_in=0.05,     # today's rainfall
    )
    # Optional fields (imputed if missing):
    #   do_mg_l, station_id, dt (datetime — defaults to now)
"""

from __future__ import annotations
import logging
import warnings
from datetime import datetime
from pathlib import Path

import json
import joblib
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MODEL_PATH = Path("ml/ecoli_model_v2.joblib")
MAPIE_PATH = Path("ml/ecoli_mapie_v2.joblib")
META_PATH  = Path("ml/ecoli_meta_v2.joblib")

EPA_THRESHOLD      = 235.0   # CFU/100mL — regulatory standard (never changes)
THRESHOLD_PATH     = Path("ml/threshold.json")  # tuned inference threshold


# ── Parameter threshold flags ─────────────────────────────────────────────────

def evaluate_parameter_flags(
    temp_c:         float | None,
    turbidity_ntu:  float | None,
    ph:             float | None,
    conductance_us: float | None,   # µS/cm
) -> list[dict]:
    """
    Evaluates each physical sensor reading against established safe ranges.
    Returns a list of warning dicts independent of the ML E. coli prediction.

    Each warning has:
        param:  which sensor triggered it
        level:  "caution" | "elevated" | "high" | "danger" | "anomaly"
        msg:    human-readable description

    Sources:
        Temperature  — National Center for Cold Water Safety / USA Swimming
        Turbidity    — EPA recreational water / state standards
        pH           — EPA aquatic life criteria (6.5–9.0)
        Conductivity — EPA freshwater baseline (50–1000 µS/cm)
    """
    flags = []

    # Temperature
    if temp_c is not None:
        if temp_c < 15:
            flags.append({
                "param": "temperature",
                "level": "danger",
                "msg":   f"Cold shock risk ({temp_c:.1f}°C) — below 15°C",
            })
        elif temp_c < 21:
            flags.append({
                "param": "temperature",
                "level": "caution",
                "msg":   f"Cold water ({temp_c:.1f}°C) — below recommended 21°C",
            })
        elif temp_c > 29:
            flags.append({
                "param": "temperature",
                "level": "caution",
                "msg":   f"Warm water ({temp_c:.1f}°C) — heat stress risk above 29°C",
            })

    # Turbidity
    if turbidity_ntu is not None:
        if turbidity_ntu > 25:
            flags.append({
                "param": "turbidity",
                "level": "high",
                "msg":   f"High turbidity ({turbidity_ntu:.1f} NTU) — above 25 NTU",
            })
        elif turbidity_ntu > 10:
            flags.append({
                "param": "turbidity",
                "level": "elevated",
                "msg":   f"Elevated turbidity ({turbidity_ntu:.1f} NTU) — above 10 NTU",
            })

    # pH
    if ph is not None:
        if ph < 6.0 or ph > 9.5:
            flags.append({
                "param": "ph",
                "level": "danger",
                "msg":   f"pH critically outside safe range ({ph:.1f}) — safe range 6.5–9.0",
            })
        elif ph < 6.5 or ph > 9.0:
            flags.append({
                "param": "ph",
                "level": "caution",
                "msg":   f"pH outside recommended range ({ph:.1f}) — safe range 6.5–9.0",
            })

    # Conductivity
    if conductance_us is not None:
        if conductance_us > 1000:
            flags.append({
                "param": "conductivity",
                "level": "elevated",
                "msg":   f"High conductivity ({conductance_us:.0f} µS/cm) — possible discharge event",
            })
        elif conductance_us < 50:
            flags.append({
                "param": "conductivity",
                "level": "anomaly",
                "msg":   f"Unusually low conductivity ({conductance_us:.0f} µS/cm) — sensor fault or heavy dilution",
            })

    return flags


# ── Predictor class ───────────────────────────────────────────────────────────

class EcoliPredictor:
    """
    Thin inference wrapper around the trained LightGBM + MAPIE pipeline.

    Thread-safe: prediction is stateless after __init__.
    Lazy-loaded so import doesn't block startup if model files are missing.
    """

    def __init__(
        self,
        model_path:     Path = MODEL_PATH,
        mapie_path:     Path = MAPIE_PATH,
        meta_path:      Path = META_PATH,
        threshold_path: Path = THRESHOLD_PATH,
    ):
        self._ready = False
        # Load tuned inference threshold (falls back to EPA 235 if file missing)
        self.inference_threshold = EPA_THRESHOLD
        if threshold_path.exists():
            try:
                with open(threshold_path) as f:
                    t = json.load(f)
                self.inference_threshold = float(t["inference_threshold_cfu"])
                logger.info(
                    "Loaded tuned threshold: %.0f CFU (EPA standard: %.0f CFU)",
                    self.inference_threshold, EPA_THRESHOLD,
                )
            except Exception as e:
                logger.warning("Could not load threshold.json: %s — using 235 CFU", e)
        else:
            logger.info("threshold.json not found — using EPA standard 235 CFU")

        try:
            self.model    = joblib.load(model_path)
            self.mapie    = joblib.load(mapie_path)
            self.meta     = joblib.load(meta_path)
            self.features = self.meta["feature_names"]
            self._ready   = True
            logger.info(
                "EcoliPredictor loaded — features: %s | coverage: %.0f%%",
                self.features, self.meta["coverage"] * 100,
            )
        except FileNotFoundError as e:
            logger.warning(
                "EcoliPredictor: model file not found — %s. Predictions disabled.", e
            )

    # ── Public API ────────────────────────────────────────────────────────────

    def predict(
        self,
        *,
        turbidity_ntu:  float | None = None,
        temperature_c:  float | None = None,
        conductance_ms: float | None = None,   # Specific Conductance (mS/cm)
        ph:             float | None = None,
        rain_day0_in:   float = 0.0,           # today's rainfall (inches)
        rain_lag1_in:   float = 0.0,           # yesterday's rainfall only
        rain_lag2_in:   float = 0.0,           # 2 days ago only
        rain_3day_cum:  float | None = None,   # computed if not supplied
        do_mg_l:        float | None = None,   # dissolved oxygen — imputed if None
        station_id:     int   = -1,            # -1 = unknown, uses median imputation
        dt:             datetime | None = None,
    ) -> dict:
        """
        Returns a dict with:
            ready, point_estimate_cfu, lower_ci_cfu, upper_ci_cfu,
            uncertainty, is_unsafe, epa_threshold_cfu, parameter_warnings
        """
        if not self._ready:
            return self._unavailable()

        if dt is None:
            dt = datetime.now()

        # Derive 3-day cumulative if not provided
        if rain_3day_cum is None:
            rain_3day_cum = rain_day0_in + rain_lag1_in + rain_lag2_in

        row = {
            "turbidity_ntu":  turbidity_ntu,
            "temperature_c":  temperature_c,
            "conductance_ms": conductance_ms,
            "ph":             ph,
            "do_mg_l":        do_mg_l,
            "rain_day0_in":   rain_day0_in,
            "rain_lag1_in":   rain_lag1_in,
            "rain_lag2_in":   rain_lag2_in,
            "rain_3day_cum":  rain_3day_cum,
            "month":          float(dt.month),
            "doy_sin":        np.sin(2 * np.pi * dt.timetuple().tm_yday / 365),
            "doy_cos":        np.cos(2 * np.pi * dt.timetuple().tm_yday / 365),
            "station_id":     float(station_id),
        }

        # Build DataFrame with exactly the columns the model expects
        X = pd.DataFrame([{f: row.get(f, np.nan) for f in self.features}])

        # Point estimate + conformal interval (suppress sklearn feature-name warning)
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="X does not have valid feature names")
            log_pred = self.model.predict(X)[0]
            _, y_pi  = self.mapie.predict_interval(X)

        point_cfu = float(np.expm1(log_pred))
        lo_cfu    = float(np.expm1(y_pi[0, 0, 0]).clip(min=0))
        hi_cfu    = float(np.expm1(y_pi[0, 1, 0]).clip(min=0))

        # Safety decision: flag unsafe if UPPER bound exceeds tuned threshold
        # Uses inference_threshold (from threshold.json) which may be lower than
        # the EPA standard of 235 CFU to further reduce FNR.
        is_unsafe   = hi_cfu > self.inference_threshold
        uncertainty = (hi_cfu - lo_cfu) / 2.0

        # Parameter threshold warnings (independent of ML model)
        # conductance_ms -> µS/cm for the flag function
        conductance_us = conductance_ms * 1000.0 if conductance_ms is not None else None
        param_warnings = evaluate_parameter_flags(
            temp_c         = temperature_c,
            turbidity_ntu  = turbidity_ntu,
            ph             = ph,
            conductance_us = conductance_us,
        )

        result = {
            "ready":               True,
            "point_estimate_cfu":  round(point_cfu, 1),
            "lower_ci_cfu":        round(lo_cfu, 1),
            "upper_ci_cfu":        round(hi_cfu, 1),
            "uncertainty":         round(uncertainty, 1),
            "is_unsafe":               is_unsafe,
            "epa_threshold_cfu":       EPA_THRESHOLD,
            "inference_threshold_cfu":  self.inference_threshold,
            "parameter_warnings":  param_warnings,
        }

        logger.info(
            "E. coli prediction: %.1f CFU [%.1f, %.1f] | unsafe=%s | warnings=%d",
            point_cfu, lo_cfu, hi_cfu, is_unsafe, len(param_warnings),
        )
        return result

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _unavailable() -> dict:
        return {
            "ready":               False,
            "point_estimate_cfu":  None,
            "lower_ci_cfu":        None,
            "upper_ci_cfu":        None,
            "uncertainty":         None,
            "is_unsafe":               None,
            "epa_threshold_cfu":       EPA_THRESHOLD,
            "inference_threshold_cfu":  EPA_THRESHOLD,
            "parameter_warnings":  [],
        }