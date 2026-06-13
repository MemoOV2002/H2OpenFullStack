"""
HTTP ingest endpoint for H2Open.
The T-Beam base station POSTs raw sensor JSON here.
Returns a safety decision the firmware uses to TX back to the buoy.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional

from app.database import get_db
from app.services.packet_processor import process_packet

router = APIRouter()


class BuoyIngestPayload(BaseModel):
    """Matches the JSON the T-Beam firmware already sends."""
    buoy_id:      str   = Field(default="BUOY_01")
    conductivity: float = Field(..., description="µS/cm")
    temperature:  float = Field(..., description="°C")
    turbidity:    float = Field(..., description="NTU")
    ph:           float = Field(..., ge=0, le=14)
    rssi:         Optional[float] = None
    snr:          Optional[float] = None
    # Extra fields the firmware sends — accepted but ignored server-side
    device_id:    Optional[str]   = None
    parse_ok:     Optional[bool]  = None
    safety:       Optional[str]   = None
    raw_packet:   Optional[str]   = None
    source:       Optional[str]   = None


class IngestResponse(BaseModel):
    is_safe:       bool
    safety_level:  str          # "GREEN" or "RED"
    ecoli_upper_ci: float
    cyano_bloom:   bool
    epa_threshold: float
    message:       str


@router.post("/ingest", response_model=IngestResponse, status_code=200)
async def ingest_reading(
    payload: BuoyIngestPayload,
    db: Session = Depends(get_db),
):
    """
    Accept a raw sensor packet from the T-Beam base station.
    Runs ML inference and returns a safety decision the firmware
    can relay back to the buoy over LoRa.
    """
    if not payload.parse_ok and payload.parse_ok is not None:
        raise HTTPException(status_code=422, detail="Firmware reported parse failure.")

    result = await process_packet(
        conductivity=payload.conductivity,
        temperature=payload.temperature,
        turbidity=payload.turbidity,
        ph=payload.ph,
        buoy_id=payload.buoy_id,
        rssi=payload.rssi,
        snr=payload.snr,
        db=db,
    )

    message = (
        "Water is SAFE for recreation."
        if result["is_safe"]
        else "Water is UNSAFE — E. coli or cyanobacteria exceeds threshold."
    )

    return IngestResponse(
        is_safe=result["is_safe"],
        safety_level=result["safety_level"],
        ecoli_upper_ci=result["ecoli_upper_ci"],
        cyano_bloom=result["cyano_bloom"],
        epa_threshold=result["epa_threshold"],
        message=message,
    )