from fastapi import APIRouter, HTTPException, Query
from app.api.endpoints.air_quality import validate_query_param
from app.schemas.map import PollutantMapResponse
from app.services.air_quality.map_service import map_service

router = APIRouter()


@router.get("/pollutants", response_model=PollutantMapResponse)
async def get_pollutant_map_distribution(
    city: str = Query(default="delhi", max_length=80, description="Metropolitan city name or ID (e.g. delhi, mumbai, bengaluru)"),
    pollutant: str = Query(default="pm25", max_length=20, description="Pollutant parameter (pm25, pm10, no2, so2, o3, co, nh3, pb)")
):
    """
    Returns geographical distribution of real monitoring stations and measured concentrations
    for the selected pollutant across the target metropolitan region.
    """
    clean_city = validate_query_param(city, "city", max_length=80, min_length=1)
    clean_pollutant = validate_query_param(pollutant, "pollutant", max_length=20, min_length=1)
    try:
        return await map_service.get_city_pollutant_map(city_identifier=clean_city, pollutant=clean_pollutant)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
