from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class StationMapPoint(BaseModel):
    station_id: str = Field(..., description="Unique station or grid coordinate identifier")
    station_name: str = Field(..., description="Official station name or grid location")
    latitude: float
    longitude: float
    concentration: Optional[float] = Field(None, description="Observed concentration; None if unmonitored")
    cpcb_sub_index: Optional[float] = Field(None, description="Calculated CPCB sub-index for this pollutant")
    sub_index_category: Literal[
        "Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe", "Unavailable"
    ] = "Unavailable"
    observed_at: datetime
    data_provider: str = Field(..., description="e.g. 'WAQI (Official CPCB Ground Feed)' or 'Open-Meteo CAMS'")
    source_type: Literal["ground_station", "atmospheric_model", "unavailable"]
    freshness_status: Literal["live", "stale", "unavailable"]
    quality_confidence: Literal["high", "moderate", "low", "unverified"]


class MapSummary(BaseModel):
    total_stations: int
    reporting_stations: int
    min_concentration: Optional[float] = None
    max_concentration: Optional[float] = None
    avg_concentration: Optional[float] = None
    data_provenance_note: str


class PollutantMapResponse(BaseModel):
    selected_city: str
    city_center_lat: float
    city_center_lng: float
    selected_pollutant: str = Field(..., description="e.g. 'pm25', 'pm10', 'no2', 'so2', 'o3', 'co', 'nh3', 'pb'")
    pollutant_name: str = Field(..., description="e.g. 'PM2.5 (Fine Particulates)'")
    unit: str = Field(..., description="e.g. 'µg/m³' or 'mg/m³'")
    stations: List[StationMapPoint]
    summary: MapSummary
