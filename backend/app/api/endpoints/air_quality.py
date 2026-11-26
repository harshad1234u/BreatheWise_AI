from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from app.schemas.air_quality import CityMetadata, NormalizedAirObservation, RegionType
from app.schemas.plan import sanitize_bounded_text
from app.services.air_quality.city_catalog import city_catalog
from app.services.air_quality.data_manager import data_manager

router = APIRouter()


def validate_query_param(
    value: Optional[str], field_name: str, max_length: int, min_length: int = 0
) -> Optional[str]:
    if value is None:
        return None
    try:
        cleaned = sanitize_bounded_text(value, field_name, max_length=max_length, min_length=min_length)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return cleaned or None


@router.get("/cities", response_model=List[CityMetadata])
async def list_cities(
    q: Optional[str] = Query(None, max_length=80, description="Search city name, alias, district, or state"),
    state: Optional[str] = Query(None, max_length=80, description="Filter by exact State or Union Territory name"),
    region_type: Optional[RegionType] = Query(None, description="Filter by 'state' or 'union_territory'"),
    limit: Optional[int] = Query(None, ge=1, le=200, description="Maximum cities to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """Returns Pan-India cities across all 28 States and 8 Union Territories with optional search/filter."""
    clean_q = validate_query_param(q, "q", max_length=80)
    clean_state = validate_query_param(state, "state", max_length=80)
    return data_manager.get_supported_cities(
        q=clean_q, state=clean_state, region_type=region_type, limit=limit, offset=offset
    )


@router.get("/cities/catalog")
async def get_cities_catalog_metadata():
    """Returns counts and lists of covered Indian States and Union Territories."""
    return city_catalog.summary_metadata()


@router.get("/air-quality", response_model=NormalizedAirObservation)
async def get_air_quality(
    city: str = Query(..., min_length=1, max_length=80, description="City ID, name, or alias from the Pan-India catalog (e.g. 'delhi', 'jaipur', 'madurai')"),
    station_id: Optional[str] = Query(None, max_length=80, description="Optional specific ground monitoring station ID")
):
    """
    Fetches real-time normalized air quality observation using the 3-Tier Ingestion Pipeline:
    Tier 1 (Ground Station) -> Tier 2 (CAMS Atmospheric Model) -> Tier 3 (Unavailable).
    """
    clean_city = validate_query_param(city, "city", max_length=80, min_length=1)
    clean_station_id = validate_query_param(station_id, "station_id", max_length=80)
    return await data_manager.get_air_quality(city_identifier=clean_city, station_id=clean_station_id)
