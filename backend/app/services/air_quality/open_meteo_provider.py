import httpx
from datetime import datetime, timezone
from typing import Optional
from app.schemas.air_quality import (
    NormalizedAirObservation,
    PollutantConcentration,
)
from app.services.air_quality.base import AirQualityProvider
from app.services.cpcb_calculator import evaluate_naqi_from_concentrations


class OpenMeteoProvider(AirQualityProvider):
    """
    Tier 2 Fallback: Open-Meteo CAMS Atmospheric Model Provider.
    Provides modeled particulate and gaseous estimates when ground telemetry is unavailable.
    """

    def __init__(self):
        self.base_url = "https://air-quality-api.open-meteo.com/v1/air-quality"

    async def get_air_quality(
        self,
        city: str,
        latitude: float,
        longitude: float,
        station_id: Optional[str] = None
    ) -> Optional[NormalizedAirObservation]:
        url = (
            f"{self.base_url}?latitude={latitude}&longitude={longitude}"
            f"&current=pm10,pm2_5,nitrogen_dioxide,sulphur_dioxide,ozone,carbon_monoxide"
        )

        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return None

                data = resp.json()
                current = data.get("current", {})
                if not current:
                    return None

                # Extract concentrations
                pollutants = {}
                
                # PM2.5
                if current.get("pm2_5") is not None:
                    pollutants["pm25"] = PollutantConcentration(
                        value=float(current["pm2_5"]),
                        unit="µg/m³",
                        averaging_period_hours=1
                    )
                
                # PM10
                if current.get("pm10") is not None:
                    pollutants["pm10"] = PollutantConcentration(
                        value=float(current["pm10"]),
                        unit="µg/m³",
                        averaging_period_hours=1
                    )

                # NO2
                if current.get("nitrogen_dioxide") is not None:
                    pollutants["no2"] = PollutantConcentration(
                        value=float(current["nitrogen_dioxide"]),
                        unit="µg/m³",
                        averaging_period_hours=1
                    )

                # SO2
                if current.get("sulphur_dioxide") is not None:
                    pollutants["so2"] = PollutantConcentration(
                        value=float(current["sulphur_dioxide"]),
                        unit="µg/m³",
                        averaging_period_hours=1
                    )

                # O3
                if current.get("ozone") is not None:
                    pollutants["o3"] = PollutantConcentration(
                        value=float(current["ozone"]),
                        unit="µg/m³",
                        averaging_period_hours=1
                    )

                # CO (Open-Meteo returns µg/m³; convert to mg/m³ for CPCB scale)
                if current.get("carbon_monoxide") is not None:
                    co_mg = round(float(current["carbon_monoxide"]) / 1000.0, 2)
                    pollutants["co"] = PollutantConcentration(
                        value=co_mg,
                        unit="mg/m³",
                        averaging_period_hours=1
                    )

                # Calculate CPCB sub-index for model estimate
                index_val, category, _, _ = evaluate_naqi_from_concentrations(
                    pollutants, has_full_24h_data=False
                )

                now_utc = datetime.now(timezone.utc)
                disclosure = (
                    "Atmospheric model estimate derived from ECMWF Copernicus (CAMS) regional reanalysis. "
                    "Ground station telemetry was offline or unavailable for this location."
                )

                return NormalizedAirObservation(
                    city=city,
                    locality_or_station=f"{city} Regional Atmospheric Grid",
                    station_distance_km=None,
                    source_type="atmospheric_model",
                    data_provider="Open-Meteo (CAMS Regional Model)",
                    observed_at=now_utc,
                    fetched_at=now_utc,
                    data_status="live",
                    confidence_score="moderate",
                    index_type="atmospheric_model_estimate",
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
