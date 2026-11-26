from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class StationMapPoint(BaseModel):
    station_id: str = Field(..., description="Unique station or grid coordinate identifier")
    station_name: str = Field(..., description="Station name or grid location")
    latitude: float
    longitude: float
    measurement_type: Literal[
        "raw_concentration",
        "provider_index",
        "cpcb_sub_index",
        "model_estimate",
        "unavailable",
    ] = "unavailable"
    concentration: Optional[float] = Field(None, description="Observed/modeled mass concentration; None if unmonitored or index-only")
    cpcb_sub_index: Optional[float] = Field(None, description="Calculated CPCB sub-index for concentration-backed readings")
    sub_index_category: Literal[
        "Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe", "Unavailable"
    ] = "Unavailable"
    provider_index: Optional[float] = Field(None, description="Provider-specific index (e.g. WAQI US-EPA AQI); not a µg/m³ concentration")
    provider_index_name: Optional[str] = Field(None, description="e.g. 'WAQI US-EPA AQI'")
    provider_index_category: Optional[str] = Field(None, description="Category label on the provider's scale")
    unavailable_reason: Optional[str] = Field(None, description="Reason when concentration or measurement is unavailable")
    observed_at: Optional[datetime] = None
    data_provider: str = Field(..., description="e.g. 'WAQI Provider Feed' or 'Open-Meteo CAMS'")
    source_type: Literal["ground_station", "atmospheric_model", "unavailable"]
    freshness_status: Literal["live", "stale", "expired", "unavailable"]
    quality_confidence: Literal["high", "moderate", "low", "unverified"]


class MapSummary(BaseModel):
    total_stations: int
    reporting_stations: int
    measurement_mode: Literal[
        "raw_concentration",
        "provider_index",
        "model_estimate",
        "mixed",
        "unavailable",
    ] = "unavailable"
    concentration_stations: int = 0
    provider_index_stations: int = 0
    model_stations: int = 0
    min_concentration: Optional[float] = None
    max_concentration: Optional[float] = None
    avg_concentration: Optional[float] = None
    min_provider_index: Optional[float] = None
    max_provider_index: Optional[float] = None
    avg_provider_index: Optional[float] = None
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
