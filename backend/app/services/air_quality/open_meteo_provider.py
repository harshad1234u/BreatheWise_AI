import math
import httpx
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
from app.schemas.air_quality import (
    NormalizedAirObservation,
    PollutantConcentration,
)
from app.services.air_quality.base import AirQualityProvider
from app.services.air_quality.freshness import evaluate_observation_freshness
from app.services.cpcb_calculator import evaluate_naqi_from_concentrations


_OPEN_METEO_POLLUTANT_MAP: Dict[str, Tuple[str, str, float]] = {
    "pm25": ("pm2_5", "µg/m³", 1.0),
    "pm10": ("pm10", "µg/m³", 1.0),
    "no2": ("nitrogen_dioxide", "µg/m³", 1.0),
    "so2": ("sulphur_dioxide", "µg/m³", 1.0),
    "o3": ("ozone", "µg/m³", 1.0),
    "co": ("carbon_monoxide", "mg/m³", 1000.0),
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_non_negative_float(raw_val: object) -> Optional[float]:
    if raw_val is None or isinstance(raw_val, bool):
        return None
    try:
        val = float(raw_val)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(val) or val < 0.0:
        return None
    return val


class OpenMeteoProvider(AirQualityProvider):
    """
    Tier 2 Fallback: Open-Meteo CAMS Atmospheric Model Provider.
    Provides modeled particulate and gaseous estimates when ground telemetry is unavailable.
    """

    def __init__(self, http_client: Optional[httpx.AsyncClient] = None):
        self.base_url = "https://air-quality-api.open-meteo.com/v1/air-quality"
        self.http_client = http_client

    async def get_air_quality(
        self,
        city: str,
        latitude: float,
        longitude: float,
        station_id: Optional[str] = None
    ) -> Optional[NormalizedAirObservation]:
        from app.core.http_client import acquire_http_client

        url = (
            f"{self.base_url}?latitude={latitude}&longitude={longitude}"
            f"&current=pm10,pm2_5,nitrogen_dioxide,sulphur_dioxide,ozone,carbon_monoxide"
        )

        try:
            async with acquire_http_client(
                injected_client=self.http_client, timeout=4.0, client_factory=httpx.AsyncClient
            ) as client:
                resp = await client.get(url, timeout=4.0)
                if resp.status_code != 200:
                    return None

                data = resp.json()
                current = data.get("current", {}) if isinstance(data, dict) else {}
                if not current or not isinstance(current, dict):
                    return None

                # Extract & validate non-negative concentrations uniformly
                pollutants: Dict[str, PollutantConcentration] = {}
                for target_key, (src_key, unit, divisor) in _OPEN_METEO_POLLUTANT_MAP.items():
                    parsed = _parse_non_negative_float(current.get(src_key))
                    if parsed is not None:
                        scaled = round(parsed / divisor, 2) if divisor != 1.0 else parsed
                        pollutants[target_key] = PollutantConcentration(
                            value=scaled,
                            unit=unit,
                            averaging_period_hours=1,
                        )

                # Calculate CPCB sub-index for model estimate (strictly flagged as model-derived)
                index_val, category, index_type, disclosure = evaluate_naqi_from_concentrations(
                    pollutants, has_full_24h_data=False, is_model_derived=True
                )

                now_utc = _utc_now().astimezone(timezone.utc)
                time_iso = current.get("time")
                observed_dt, freshness, freshness_note = evaluate_observation_freshness(
                    time_iso if isinstance(time_iso, str) else None,
                    now_utc=now_utc,
                )
                observed_at = observed_dt or now_utc

                if freshness == "live":
                    data_status = "live"
                    confidence = "moderate"
                elif freshness == "stale":
                    data_status = "stale"
                    confidence = "low"
                elif freshness == "expired":
                    data_status = "unavailable"
                    confidence = "low"
                else:
                    data_status = "unavailable"
                    confidence = "unverified"

                if freshness_note:
                    disclosure = f"{disclosure} Freshness notice: {freshness_note}."

                return NormalizedAirObservation(
                    city=city,
                    locality_or_station=f"{city} Regional Atmospheric Grid",
                    station_distance_km=None,
                    source_type="atmospheric_model",
                    data_provider="Open-Meteo (CAMS Regional Model)",
                    observed_at=observed_at,
                    fetched_at=now_utc,
                    data_status=data_status,
                    confidence_score=confidence,
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
                    nh3=pollutants.get("nh3"),
                    pb=pollutants.get("pb"),
                )

        except Exception:
            return None
