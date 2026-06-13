"""
ML prediction endpoints.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class PredictionRequest(BaseModel):
    temperature: Optional[float] = None
    dissolved_oxygen: Optional[float] = None
    do_pct_saturation: Optional[float] = None
    ph: Optional[float] = None
    turbidity: Optional[float] = None
    salinity: Optional[float] = None
    conductance: Optional[float] = None
    rainfall_1day: float = 0.0
    rainfall_2day: float = 0.0
    rainfall_3day: float = 0.0
    station_id: Optional[str] = None
    sample_datetime: Optional[datetime] = None


class PredictionResponse(BaseModel):
    predicted_ecoli_cfu: float
    is_safe: bool
    model_mae_cfu: Optional[float]


@router.post("/predict", response_model=PredictionResponse)
async def predict_ecoli(request: PredictionRequest):
    """
    Predict E. coli (CFU/100mL) from physical water quality measurements.

    The model must be trained before this endpoint is usable.
    Run `python -m ml.train` from the backend/ directory.
    """
    try:
        from ml.predict import predict
        result = predict(
            temperature=request.temperature,
            dissolved_oxygen=request.dissolved_oxygen,
            do_pct_saturation=request.do_pct_saturation,
            ph=request.ph,
            turbidity=request.turbidity,
            salinity=request.salinity,
            conductance=request.conductance,
            rainfall_1day=request.rainfall_1day,
            rainfall_2day=request.rainfall_2day,
            rainfall_3day=request.rainfall_3day,
            station_id=request.station_id,
            sample_datetime=request.sample_datetime,
        )
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/predict/status")
async def prediction_status():
    """Check whether the ML model has been trained and is ready."""
    from ml.predict import model_loaded
    ready = model_loaded()
    return {
        "model_ready": ready,
        "message": "Model is ready." if ready else "Run `python -m ml.train` to train the model.",
    }
