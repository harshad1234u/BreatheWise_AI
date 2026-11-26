import httpx
from datetime import datetime, timezone
from typing import Optional
from app.core.config import settings
from app.core.http_client import acquire_http_client
from app.schemas.air_quality import (
    NormalizedAirObservation,
    PollutantConcentration,
)
from app.services.air_quality.base import AirQualityProvider
from app.services.air_quality.freshness import (
    evaluate_observation_freshness,
    map_us_epa_aqi_to_display_category,
    map_us_epa_to_safety_severity,
)


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

    def __init__(self, api_token: Optional[str] = None, http_client: Optional[httpx.AsyncClient] = None):
        self.api_token = api_token or settings.WAQI_API_TOKEN
        self.base_url = "https://api.waqi.info/feed"
        self.http_client = http_client

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
            async with acquire_http_client(
                injected_client=self.http_client, timeout=4.0, client_factory=httpx.AsyncClient
            ) as client:
                response = await client.get(url, timeout=4.0)
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
                    us_epa_category = map_us_epa_aqi_to_display_category(index_val)
                    category = map_us_epa_to_safety_severity(index_val)
                    disclosure = (
                        f"Provider Index ({index_val}, '{us_epa_category}' on US-EPA AQI scale) reported by WAQI. "
                        f"WAQI /feed/ returns normalized US-EPA AQI sub-indices (iaqi) rather than raw "
                        f"µg/m³ or mg/m³ mass concentrations; therefore CPCB concentration breakpoint "
                        f"conversion was intentionally omitted and conservative safety-tier mapping is applied."
                    )
                else:
                    index_type = "unavailable"
                    us_epa_category = None
                    category = "Unavailable"
                    disclosure = (
                        "WAQI feed did not return a valid numeric AQI or raw mass concentrations "
                        "for CPCB breakpoint evaluation."
                    )

                # Parse timestamps per PRD v1.2 freshness policy:
                # <=3h: live | 3-12h: stale | >12h: expired (ineligible as current ground telemetry -> trigger Tier 2 model fallback)
                time_iso = payload.get("time", {}).get("iso")
                now_utc = datetime.now(timezone.utc)
                observed_dt, freshness, freshness_note = evaluate_observation_freshness(time_iso, now_utc=now_utc)
                observed_at = observed_dt or now_utc
                if freshness == "live":
                    data_status = "live"
                    confidence = "high"
                elif freshness == "stale":
                    data_status = "stale"
                    confidence = "moderate"
                elif freshness == "expired":
                    data_status = "unavailable"
                    confidence = "low"
                else:
                    data_status = "partial"
                    confidence = "low"

                if freshness_note:
                    disclosure = f"{disclosure} Freshness notice: {freshness_note}."

                # Attributions & station name (only mention CPCB/SPCB if verified in attribution metadata)
                station_name = payload.get("city", {}).get("name", f"{city} Ground Station")
                attributions = payload.get("attributions", [])
                attr_names = [a.get("name", "") for a in attributions if isinstance(a, dict) and a.get("name")]
                provider_label = "WAQI Provider Feed"
                if any(kw in a for a in attr_names for kw in ("CPCB", "SPCB", "Pollution Control")):
                    provider_label = "WAQI Feed (CPCB/SPCB Station Network)"

                return NormalizedAirObservation(
                    city=city,
                    locality_or_station=station_name,
                    station_distance_km=None,
                    source_type="ground_station",
                    data_provider=provider_label,
                    observed_at=observed_at,
                    fetched_at=now_utc,
                    data_status=data_status,
                    confidence_score=confidence,
                    index_type=index_type,
                    index_value=index_val,
                    index_category=category,
                    provider_index_category=us_epa_category,
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
