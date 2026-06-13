"""
API routes for buoy status and system health
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import BuoyStatus
from app.schemas import BuoyStatusResponse

router = APIRouter()


@router.get("/status", response_model=List[BuoyStatusResponse])
async def get_all_buoy_status(db: Session = Depends(get_db)):
    """
    Get status of all buoys in the system
    Shows which buoys are online and their latest readings
    """
    buoys = db.query(BuoyStatus).all()
    return buoys


@router.get("/status/{buoy_id}", response_model=BuoyStatusResponse)
async def get_buoy_status(
    buoy_id: str,
    db: Session = Depends(get_db)
):
    """
    Get status of a specific buoy
    
    Returns:
    - Latest reading info
    - Online/offline status
    - Battery level
    - Location
    """
    buoy = db.query(BuoyStatus).filter(BuoyStatus.buoy_id == buoy_id).first()
    
    if not buoy:
        raise HTTPException(status_code=404, detail=f"Buoy {buoy_id} not found")
    
    return buoy


@router.get("/buoys", response_model=List[str])
async def get_all_buoy_ids(db: Session = Depends(get_db)):
    """
    Get list of all registered buoy IDs
    Useful for frontend dropdowns and navigation
    """
    buoys = db.query(BuoyStatus.buoy_id).all()
    return [buoy[0] for buoy in buoys]
