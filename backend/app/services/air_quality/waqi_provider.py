import httpx
from datetime import datetime, timezone
from typing import Optional
from app.core.config import settings
from app.schemas.air_quality import (
    NormalizedAirObservation,
    PollutantConcentration,
)
from app.services.air_quality.base import AirQualityProvider
from app.services.cpcb_calculator import get_aqi_category


class WAQIProvider(AirQualityProvider):
    """
    Tier 1 Primary: World Air Quality Index (WAQI) Provider.
    Aggregates ground-station telemetry from CPCB and State PCBs across Indian cities.

    IMPORTANT DATA SEMANTICS (aqicn.org/json-api/doc/):
    WAQI `/feed/` returns `data.aqi` (overall station US-EPA AQI) and `data.iaqi[key].v`
    (individual US-EPA AQI sub-indices), NOT raw physical mass concentrations in µg/m³ or mg/m³.
    Therefore, this provider MUST NOT label `iaqi` values as µg/m³ or mg/m³ and MUST NOT pass
    US-EPA sub-indices into CPCB concentration breakpoint formulas.
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

                # WAQI iaqi values are US-EPA AQI sub-indices (dimensionless), NOT raw concentrations.
                # Preserve them with honest "US-EPA Sub-Index" unit semantics and sub_index=None
                # (CPCB concentration breakpoint calculation is intentionally not executed on sub-indices).
                pollutants = {}
                for key in ["pm25", "pm10", "no2", "so2", "co", "o3", "nh3", "pb"]:
                    if key in iaqi and isinstance(iaqi[key], dict) and iaqi[key].get("v") is not None:
                        try:
                            val = float(iaqi[key]["v"])
                        except (TypeError, ValueError):
                            pollutants[key] = None
                            continue
                        pollutants[key] = PollutantConcentration(
                            value=val,
                            unit="US-EPA Sub-Index",
                            averaging_period_hours=8 if key in ["co", "o3"] else 1,
                            sub_index=None,
                        )
                    else:
                        pollutants[key] = None

                # Parse WAQI overall provider AQI (US-EPA scale)
                raw_aqi = payload.get("aqi")
                index_val: Optional[int] = None
                if isinstance(raw_aqi, (int, float)) or (
                    isinstance(raw_aqi, str) and raw_aqi.strip().lstrip("-").isdigit()
                ):
                    parsed = int(round(float(raw_aqi)))
                    if parsed >= 0:
                        index_val = parsed

                if index_val is not None:
                    index_type = "provider_index"
                    category = get_aqi_category(index_val)
                    disclosure = (
                        f"Provider Index ({index_val}, US-EPA AQI scale) reported by WAQI. "
                        f"WAQI /feed/ returns normalized US-EPA AQI sub-indices (iaqi) rather than raw "
                        f"µg/m³ or mg/m³ mass concentrations; therefore CPCB concentration breakpoint "
                        f"conversion was intentionally omitted."
                    )
                else:
                    index_type = "unavailable"
                    category = "Unavailable"
                    disclosure = (
                        "WAQI feed did not return a valid numeric AQI or raw mass concentrations "
                        "for CPCB breakpoint evaluation."
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
                    nh3=pollutants.get("nh3"),
                    pb=pollutants.get("pb"),
                )

        except Exception:
            return None
