"""
API routes for sensor readings
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from app.database import get_db
from app.models import SensorReading, BuoyStatus
from app.schemas import SensorReadingCreate, SensorReadingResponse, SafetyDecision

router = APIRouter()

EPA_THRESHOLD = 235.0  # CFU/100mL


@router.post("/readings", response_model=SensorReadingResponse, status_code=201)
async def create_reading(reading: SensorReadingCreate, db: Session = Depends(get_db)):
    is_safe = reading.ecoli_cfu < EPA_THRESHOLD

    db_reading = SensorReading(
        buoy_id=reading.buoy_id,
        ecoli_cfu=reading.ecoli_cfu,
        is_safe=is_safe,
        conductivity=reading.conductivity,
        temperature=reading.temperature,
        turbidity=reading.turbidity,
        ph=reading.ph,
        latitude=reading.latitude,
        longitude=reading.longitude,
    )
    db.add(db_reading)
    db.commit()
    db.refresh(db_reading)

    _upsert_buoy_status(db, reading.buoy_id, reading.ecoli_cfu, is_safe)
    return db_reading


@router.get("/readings", response_model=List[SensorReadingResponse])
async def get_readings(
    buoy_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    hours: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
):
    query = db.query(SensorReading)
    if buoy_id:
        query = query.filter(SensorReading.buoy_id == buoy_id)
    if hours:
        query = query.filter(SensorReading.timestamp >= datetime.now() - timedelta(hours=hours))
    return query.order_by(SensorReading.timestamp.desc()).limit(limit).all()


@router.get("/readings/latest/{buoy_id}", response_model=SensorReadingResponse)
async def get_latest_reading(buoy_id: str, db: Session = Depends(get_db)):
    reading = (
        db.query(SensorReading)
        .filter(SensorReading.buoy_id == buoy_id)
        .order_by(SensorReading.timestamp.desc())
        .first()
    )
    if not reading:
        raise HTTPException(status_code=404, detail=f"No readings for buoy {buoy_id}")
    return reading


@router.get("/readings/{reading_id}", response_model=SensorReadingResponse)
async def get_reading(reading_id: int, db: Session = Depends(get_db)):
    reading = db.query(SensorReading).filter(SensorReading.id == reading_id).first()
    if not reading:
        raise HTTPException(status_code=404, detail=f"Reading {reading_id} not found")
    return reading


@router.get("/safety/{buoy_id}", response_model=SafetyDecision)
async def check_water_safety(buoy_id: str, db: Session = Depends(get_db)):
    reading = (
        db.query(SensorReading)
        .filter(SensorReading.buoy_id == buoy_id)
        .order_by(SensorReading.timestamp.desc())
        .first()
    )
    if not reading:
        raise HTTPException(status_code=404, detail=f"No readings for buoy {buoy_id}")

    return SafetyDecision(
        buoy_id=buoy_id,
        is_safe=reading.is_safe,
        ecoli_cfu=reading.ecoli_cfu,
        epa_threshold=EPA_THRESHOLD,
        message="Water is SAFE for recreation" if reading.is_safe else "Water is UNSAFE — E. coli exceeds EPA threshold",
        timestamp=reading.timestamp,
    )


def _upsert_buoy_status(db: Session, buoy_id: str, ecoli_cfu: float, is_safe: bool):
    status = db.query(BuoyStatus).filter(BuoyStatus.buoy_id == buoy_id).first()
    now = datetime.now()
    if status:
        status.last_reading_time = now
        status.last_ecoli_cfu = ecoli_cfu
        status.is_safe = is_safe
        status.is_online = True
        status.last_heartbeat = now
    else:
        db.add(BuoyStatus(
            buoy_id=buoy_id,
            last_reading_time=now,
            last_ecoli_cfu=ecoli_cfu,
            is_safe=is_safe,
            is_online=True,
            last_heartbeat=now,
        ))
    db.commit()