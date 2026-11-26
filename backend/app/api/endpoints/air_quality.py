from typing import List, Optional
from fastapi import APIRouter, Query
from app.schemas.air_quality import CityMetadata, NormalizedAirObservation
from app.services.air_quality.city_catalog import city_catalog
from app.services.air_quality.data_manager import data_manager

router = APIRouter()


@router.get("/cities", response_model=List[CityMetadata])
async def list_cities(
    q: Optional[str] = Query(None, description="Search city name, alias, district, or state"),
    state: Optional[str] = Query(None, description="Filter by exact State or Union Territory name"),
    region_type: Optional[str] = Query(None, description="Filter by 'state' or 'union_territory'"),
    limit: Optional[int] = Query(None, ge=1, le=200, description="Maximum cities to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """Returns Pan-India cities across all 28 States and 8 Union Territories with optional search/filter."""
    return data_manager.get_supported_cities(
        q=q, state=state, region_type=region_type, limit=limit, offset=offset
    )


@router.get("/cities/catalog")
async def get_cities_catalog_metadata():
    """Returns counts and lists of covered Indian States and Union Territories."""
    return city_catalog.summary_metadata()


@router.get("/air-quality", response_model=NormalizedAirObservation)
async def get_air_quality(
    city: str = Query(..., description="City ID, name, or alias from the Pan-India catalog (e.g. 'delhi', 'jaipur', 'madurai')"),
    station_id: Optional[str] = Query(None, description="Optional specific ground monitoring station ID")
):
    """
    Fetches real-time normalized air quality observation using the 3-Tier Ingestion Pipeline:
    Tier 1 (Ground Station) -> Tier 2 (CAMS Atmospheric Model) -> Tier 3 (Unavailable).
    """
    return await data_manager.get_air_quality(city_identifier=city, station_id=station_id)
