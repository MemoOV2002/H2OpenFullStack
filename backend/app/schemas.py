"""
Pydantic schemas for request validation and response serialization
"""
from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional


class SensorReadingCreate(BaseModel):
    """Used by the REST endpoint for manual POSTs. Serial path bypasses this."""
    buoy_id: str
    ecoli_cfu: float = Field(..., ge=0)
    conductivity: Optional[float] = Field(None, ge=0)
    temperature:  Optional[float] = None
    turbidity:    Optional[float] = Field(None, ge=0)
    ph:           Optional[float] = Field(None, ge=0, le=14)
    latitude:     Optional[float] = Field(None, ge=-90, le=90)
    longitude:    Optional[float] = Field(None, ge=-180, le=180)

    @validator('ecoli_cfu')
    def validate_ecoli(cls, v):
        if v > 100000:
            raise ValueError('E. coli count exceeds reasonable limit')
        return v


class SensorReadingResponse(BaseModel):
    id: int
    buoy_id: str
    timestamp: datetime
    ecoli_cfu: float
    is_safe: bool
    cyano_bloom: Optional[bool] = None
    conductivity: Optional[float]
    temperature:  Optional[float]
    turbidity:    Optional[float]
    ph:           Optional[float]
    rssi:         Optional[float]   # stored in DB, returned in API, not shown on frontend
    latitude:     Optional[float]
    longitude:    Optional[float]
    created_at:   datetime

    class Config:
        from_attributes = True


class BuoyStatusResponse(BaseModel):
    buoy_id: str
    last_reading_time: Optional[datetime]
    last_ecoli_cfu:    Optional[float]
    is_safe:           Optional[bool]
    is_online:         bool
    last_heartbeat:    datetime
    battery_level:     Optional[float]
    latitude:          Optional[float]
    longitude:         Optional[float]
    location_name:     Optional[str]

    class Config:
        from_attributes = True


class SafetyDecision(BaseModel):
    buoy_id: str
    is_safe: bool
    ecoli_cfu: float
    epa_threshold: float = 235.0
    message: str
    timestamp: datetime


class HealthCheck(BaseModel):
    status: str
    database: str
    websocket: str
    timestamp: datetime = Field(default_factory=datetime.now)