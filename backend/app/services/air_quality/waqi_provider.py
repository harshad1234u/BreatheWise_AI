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


class WAQIProvider(AirQualityProvider):
    """
    Tier 1 Primary: World Air Quality Index (WAQI) Provider.
    Aggregates ground-station telemetry from CPCB and State PCBs across Indian cities.
    """

    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token or settings.WAQI_API_TOKEN
        self.base_url = "https://api.waqi.info/feed"

    async def get_air_quality(
        self,
        city: str,
        latitude: float,
        longitude: float,
        station_id: Optional[str] = None
    ) -> Optional[NormalizedAirObservation]:
        if not self.api_token:
            return None

        # Prefer station_id or geo coordinates for precision
        if station_id and station_id.startswith("@"):
            url = f"{self.base_url}/{station_id}/?token={self.api_token}"
        else:
            url = f"{self.base_url}/geo:{latitude};{longitude}/?token={self.api_token}"

        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    return None

                data = response.json()
                if data.get("status") != "ok" or not data.get("data"):
                    return None

                payload = data["data"]
                iaqi = payload.get("iaqi", {})

                # Extract pollutant concentrations
                pollutants = {}
                for key in ["pm25", "pm10", "no2", "so2", "co", "o3"]:
                    if key in iaqi and "v" in iaqi[key]:
                        # CO in WAQI is typically reported in ppm or mg/m3; standardizing to mg/m3
                        val = float(iaqi[key]["v"])
                        pollutants[key] = PollutantConcentration(
                            value=val,
                            unit="mg/m³" if key == "co" else "µg/m³",
                            averaging_period_hours=8 if key in ["co", "o3"] else 1
                        )
                    else:
                        pollutants[key] = None

                # Calculate CPCB NAQI sub-index
                index_val, category, index_type, disclosure = evaluate_naqi_from_concentrations(
                    pollutants, has_full_24h_data=False
                )

                # Parse timestamps
                time_iso = payload.get("time", {}).get("iso")
                if time_iso:
                    try:
                        observed_at = datetime.fromisoformat(time_iso.replace("Z", "+00:00"))
                    except Exception:
                        observed_at = datetime.now(timezone.utc)
                else:
                    observed_at = datetime.now(timezone.utc)

                now_utc = datetime.now(timezone.utc)
                # Check freshness (older than 3 hours considered stale)
                age_hours = (now_utc - observed_at.astimezone(timezone.utc)).total_seconds() / 3600.0
                data_status = "stale" if age_hours > settings.GROUND_DATA_FRESHNESS_HOURS else "live"

                # Attributions & station name
                station_name = payload.get("city", {}).get("name", f"{city} Ground Station")
                attributions = payload.get("attributions", [])
                attr_names = [a.get("name", "") for a in attributions if a.get("name")]
                provider_label = "WAQI (CPCB / SPCB Feed)"
                if any("CPCB" in a for a in attr_names):
                    provider_label = "WAQI (Official CPCB Ground Feed)"

                return NormalizedAirObservation(
                    city=city,
                    locality_or_station=station_name,
                    station_distance_km=None,
                    source_type="ground_station",
                    data_provider=provider_label,
                    observed_at=observed_at,
                    fetched_at=now_utc,
                    data_status=data_status,
                    confidence_score="high" if data_status == "live" else "moderate",
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
