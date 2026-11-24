from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from app.schemas.air_quality import CityMetadata, NormalizedAirObservation
from app.services.air_quality.data_manager import data_manager

router = APIRouter()


@router.get("/cities", response_model=List[CityMetadata])
async def list_cities():
    """Returns list of supported Indian metro cities with coordinates."""
    return data_manager.get_supported_cities()


@router.get("/air-quality", response_model=NormalizedAirObservation)
async def get_air_quality(
    city: str = Query(..., description="Name or identifier of supported city (e.g. 'delhi', 'mumbai')"),
    station_id: Optional[str] = Query(None, description="Optional specific ground monitoring station ID")
):
    """
    Fetches real-time normalized air quality observation using the 3-Tier Ingestion Pipeline:
    Tier 1 (Ground Station) -> Tier 2 (CAMS Atmospheric Model) -> Tier 3 (Unavailable).
    """
    observation = await data_manager.get_air_quality(city_identifier=city, station_id=station_id)
    return observation
