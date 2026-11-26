from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class HourlyPollutantPoint(BaseModel):
    timestamp: str = Field(..., description="ISO 8601 hourly timestamp e.g. '2026-11-24T06:00'")
    hour_label: str = Field(..., description="Human-readable hour e.g. '06:00', '14:00'")
    pm25: Optional[float] = Field(None, description="Modeled PM2.5 concentration in µg/m³")
    pm10: Optional[float] = Field(None, description="Modeled PM10 concentration in µg/m³")
    o3: Optional[float] = Field(None, description="Modeled O3 concentration in µg/m³")
    no2: Optional[float] = Field(None, description="Modeled NO2 concentration in µg/m³")
    so2: Optional[float] = Field(None, description="Modeled SO2 concentration in µg/m³")
    co: Optional[float] = Field(None, description="Modeled CO concentration in mg/m³")
    wind_speed: Optional[float] = Field(None, description="Wind speed in km/h if available")
    comparative_score: float = Field(..., description="Max CPCB sub-index for available pollutants at this hour")
    dominant_pollutant: str = Field(..., description="Pollutant driving the comparative score (e.g. 'pm25')")
    category_label: str = Field(..., description="CPCB band equivalent (e.g. 'Moderate', 'Poor')")


class BestAirWindowPeriod(BaseModel):
    start_time: str = Field(..., description="Window start time e.g. '06:00'")
    end_time: str = Field(..., description="Window end time e.g. '07:00'")
    start_iso: Optional[str] = None
    end_iso: Optional[str] = None
    duration_hours: int = 1
    average_comparative_score: float
    score_label: Literal[
        "Lowest Forecast Pollution Period",
        "Comparatively Better Window",
        "Higher Pollution Period",
        "Insufficient Forecast Data"
    ]
    dominant_pollutant: str
    strenuous_outdoor_allowed: bool
    activity_suitability: str
    precautionary_notes: List[str] = []


class AirWindowResponse(BaseModel):
    city: str
    activity: str
    duration_hours: int
    generated_at: datetime
    data_provider: str = "Open-Meteo Atmospheric Chemistry (CAMS & ECMWF)"
    data_provenance_type: Literal["atmospheric_model", "unavailable"] = "atmospheric_model"
    confidence: Literal["moderate", "low", "unverified"] = "moderate"
    status: Literal["available", "insufficient_data", "unavailable"] = "available"
    disclaimer: str = (
        "Notice: This window is an internal comparative indicator derived from atmospheric chemistry "
        "model forecasts (Open-Meteo / ECMWF CAMS). It is not an official CPCB NAQI measurement nor an "
        "absolute exposure certification."
    )
    
    # Primary Recommended Window
    best_window: Optional[BestAirWindowPeriod] = None
    
    # Peak / Highest Pollution Period to avoid
    peak_pollution_window: Optional[BestAirWindowPeriod] = None
    
    # Alternate viable windows
    alternative_windows: List[BestAirWindowPeriod] = []
    
    # Hourly trajectory for 24 to 48 hours
    hourly_forecast: List[HourlyPollutantPoint] = []
