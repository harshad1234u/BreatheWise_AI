from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from app.api.endpoints.air_quality import validate_query_param
from app.schemas.air_window import AirWindowResponse
from app.services.air_quality.air_window import air_window_service

router = APIRouter()


@router.get("/air-window", response_model=AirWindowResponse)
async def get_best_air_window(
    city: str = Query(..., max_length=80, description="Target metropolitan area e.g. 'Delhi', 'Mumbai', 'Bengaluru'"),
    activity: str = Query(default="general_outdoor", max_length=60, description="Activity e.g. 'running', 'walking', 'cycling', 'commute', 'ventilation'"),
    duration: Optional[int] = Query(default=None, ge=1, le=3, description="Duration in hours (1 to 3)"),
    is_vulnerable: bool = Query(default=False, description="Flag indicating respiratory or cardiovascular sensitivity"),
):
    """
    Computes the multi-pollutant comparative Best Air Window using Open-Meteo CAMS atmospheric forecasts.
    Evaluates sliding diurnal periods across PM2.5, PM10, O3, NO2, SO2, and CO to identify
    comparatively lower relative pollutant exposure windows without declaring any outdoor air 'Safe'.
    """
    if not city or not city.strip():
        raise HTTPException(status_code=400, detail="City parameter cannot be empty.")

    clean_city = validate_query_param(city, "city", max_length=80, min_length=1)
    clean_activity = validate_query_param(activity, "activity", max_length=60, min_length=1)

    return await air_window_service.calculate_best_window(
        city_identifier=clean_city,
        activity=clean_activity,
        duration_hours=duration,
        is_vulnerable=is_vulnerable,
    )
