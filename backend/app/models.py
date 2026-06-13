"""
Database models for H2Open system
"""
from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean
from sqlalchemy.sql import func
from app.database import Base


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, index=True)
    buoy_id = Column(String, index=True, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # ML-derived water quality output
    ecoli_cfu = Column(Float, nullable=False)   # CFU/100mL — predicted by ML model
    is_safe = Column(Boolean, nullable=False)   # True if ecoli_cfu < 235 EPA threshold
    cyano_bloom  = Column(Boolean, nullable=True)   # cyanobacteria bloom prediction

    # Physical sensor readings (direct from buoy packet)
    conductivity = Column(Float, nullable=True)  # μS/cm
    temperature  = Column(Float, nullable=True)  # °C
    turbidity    = Column(Float, nullable=True)  # NTU
    ph           = Column(Float, nullable=True)

    # Signal health — stored for diagnostics, not displayed on frontend
    rssi = Column(Float, nullable=True)          # dBm

    # Location
    latitude  = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<SensorReading(buoy={self.buoy_id}, ecoli={self.ecoli_cfu}, safe={self.is_safe})>"


class BuoyStatus(Base):
    __tablename__ = "buoy_status"

    id = Column(Integer, primary_key=True, index=True)
    buoy_id = Column(String, unique=True, index=True, nullable=False)

    last_reading_time = Column(DateTime(timezone=True))
    last_ecoli_cfu    = Column(Float)
    is_safe           = Column(Boolean)

    is_online       = Column(Boolean, default=True)
    last_heartbeat  = Column(DateTime(timezone=True), server_default=func.now())
    battery_level   = Column(Float, nullable=True)

    latitude      = Column(Float, nullable=True)
    longitude     = Column(Float, nullable=True)
    location_name = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<BuoyStatus(buoy={self.buoy_id}, online={self.is_online}, safe={self.is_safe})>"