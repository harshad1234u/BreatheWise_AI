from fastapi import APIRouter, Query
from app.schemas.map import PollutantMapResponse
from app.services.air_quality.map_service import map_service

router = APIRouter()


@router.get("/pollutants", response_model=PollutantMapResponse)
async def get_pollutant_map_distribution(
    city: str = Query(default="delhi", description="Metropolitan city name or ID (e.g. delhi, mumbai, bengaluru)"),
    pollutant: str = Query(default="pm25", description="Pollutant parameter (pm25, pm10, no2, so2, o3, co, nh3, pb)")
):
    """
    Returns geographical distribution of real monitoring stations and measured concentrations
    for the selected pollutant across the target metropolitan region.
    """
    return await map_service.get_city_pollutant_map(city_identifier=city, pollutant=pollutant)
