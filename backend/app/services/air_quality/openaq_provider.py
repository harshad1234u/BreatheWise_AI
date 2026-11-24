import httpx
from datetime import datetime, timezone
from typing import Optional
from app.core.config import settings
from app.schemas.air_quality import (
    NormalizedAirObservation,
    PollutantConcentration,
)
from app.services.air_quality.base import AirQualityProvider
from app.services.cpcb_calculator import evaluate_naqi_from_concentrations


class OpenAQProvider(AirQualityProvider):
    """
    Tier 1 Secondary: OpenAQ v3 API Provider.
    Queries global open ground monitoring stations as a secondary ground-truth backup.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.OPENAQ_API_KEY
        self.base_url = "https://api.openaq.org/v3"

    async def get_air_quality(
        self,
        city: str,
        latitude: float,
        longitude: float,
        station_id: Optional[str] = None
    ) -> Optional[NormalizedAirObservation]:
        if not self.api_key:
            return None

        headers = {"X-API-Key": self.api_key}

        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                # Find nearest location within 25km
                search_url = f"{self.base_url}/locations?coordinates={latitude},{longitude}&radius=25000&limit=1"
                resp = await client.get(search_url, headers=headers)
                if resp.status_code != 200:
                    return None

                results = resp.json().get("results", [])
                if not results:
                    return None

                location = results[0]
                loc_id = location.get("id")
                station_name = location.get("name", f"{city} OpenAQ Monitor")

                # Get latest measurements for this location
                latest_url = f"{self.base_url}/locations/{loc_id}/latest"
                latest_resp = await client.get(latest_url, headers=headers)
                if latest_resp.status_code != 200:
                    return None

                measurements = latest_resp.json().get("results", [])
                pollutants = {}

                for m in measurements:
                    param = m.get("parameter", {}).get("name", "").lower()
                    val = m.get("value")
                    unit = m.get("parameter", {}).get("units", "µg/m³")

                    if param in ["pm25", "pm10", "no2", "so2", "co", "o3"] and val is not None:
                        pollutants[param] = PollutantConcentration(
                            value=float(val),
                            unit=unit,
                            averaging_period_hours=1
                        )

                if not pollutants:
                    return None

                index_val, category, index_type, disclosure = evaluate_naqi_from_concentrations(
                    pollutants, has_full_24h_data=False
                )

                now_utc = datetime.now(timezone.utc)
                return NormalizedAirObservation(
                    city=city,
                    locality_or_station=station_name,
                    station_distance_km=None,
                    source_type="ground_station",
                    data_provider="OpenAQ Ground Telemetry",
                    observed_at=now_utc,
                    fetched_at=now_utc,
                    data_status="live",
                    confidence_score="high",
                    index_type=index_type,
                    index_value=index_val,
                    index_category=category,
                    methodology_disclosure=disclosure,
                    pm25=pollutants.get("pm25"),
                    pm10=pollutants.get("pm10"),
                    no2=pollutants.get("no2"),
                    so2=pollutants.get("so2"),
                    co=pollutants.get("co"),
                    o3=pollutants.get("o3"),
                )

        except Exception:
            return None
