from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class PollutantConcentration(BaseModel):
    value: float = Field(..., description="Observed or modeled concentration value")
    unit: str = Field(default="µg/m³", description="Measurement unit (e.g. µg/m³, mg/m³)")
    averaging_period_hours: int = Field(default=1, description="Averaging period of the input data (1, 8, or 24)")
    sub_index: Optional[float] = Field(None, description="Calculated CPCB sub-index for this pollutant")
    source_unit: Optional[str] = Field(None, description="Original provider unit before normalization")
    is_converted: bool = Field(
        default=False,
        description="True when value was converted from ppb/ppm using standard 25°C, 1 atm approximation",
    )


class NormalizedAirObservation(BaseModel):
    city: str
    locality_or_station: Optional[str] = None
    station_distance_km: Optional[float] = None
    
    # Rigorous Provenance & Status Tracking
    source_type: Literal["ground_station", "atmospheric_model", "stale_cache", "unavailable"]
    data_provider: str = Field(..., description="e.g., 'WAQI (CPCB Feed)', 'OpenAQ', 'Open-Meteo CAMS'")
    observed_at: datetime
    fetched_at: datetime
    data_status: Literal["live", "stale", "partial", "unavailable"]
    confidence_score: Literal["high", "moderate", "low", "unverified"]
    
    # Official vs Indicative Index Distinctions (Safeguard A)
    index_type: Literal[
        "official_cpcb_naqi",
        "indicative_particulate_subindex",
        "provider_index",
        "atmospheric_model_estimate",
        "unavailable"
    ]
    index_value: Optional[int] = None
    index_category: Literal["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe", "Unavailable"]
    provider_index_category: Optional[str] = Field(
        None,
        description="Explicit category on provider's native scale (e.g. 'Unhealthy' for WAQI US-EPA AQI)",
    )
    methodology_disclosure: str = Field(..., description="Transparent explanation of how index was determined")
    
    # Criteria Pollutants (All 8 Official CPCB Parameters)
    pm25: Optional[PollutantConcentration] = None
    pm10: Optional[PollutantConcentration] = None
    no2: Optional[PollutantConcentration] = None
    so2: Optional[PollutantConcentration] = None
    co: Optional[PollutantConcentration] = None
    o3: Optional[PollutantConcentration] = None
    nh3: Optional[PollutantConcentration] = None
    pb: Optional[PollutantConcentration] = None


RegionType = Literal["state", "union_territory"]


class CityMetadata(BaseModel):
    id: str
    name: str
    state: str
    region_type: RegionType = "state"
    district: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    latitude: float
    longitude: float
    waqi_keyword: str = ""
    availability_status: Literal[
        "ground_monitoring_available",
        "model_forecast_available",
        "both_available",
        "no_current_data",
        "unsupported_location",
    ] = "model_forecast_available"
