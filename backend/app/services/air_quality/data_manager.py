from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from app.core.config import settings
from app.schemas.air_quality import CityMetadata, NormalizedAirObservation
from app.services.air_quality.open_meteo_provider import OpenMeteoProvider
from app.services.air_quality.openaq_provider import OpenAQProvider
from app.services.air_quality.waqi_provider import WAQIProvider

SUPPORTED_CITIES: List[CityMetadata] = [
    CityMetadata(
        id="delhi",
        name="Delhi NCR",
        state="Delhi",
        latitude=28.6139,
        longitude=77.2090,
        waqi_keyword="delhi"
    ),
    CityMetadata(
        id="mumbai",
        name="Mumbai",
        state="Maharashtra",
        latitude=19.0760,
        longitude=72.8777,
        waqi_keyword="mumbai"
    ),
    CityMetadata(
        id="bengaluru",
        name="Bengaluru",
        state="Karnataka",
        latitude=12.9716,
        longitude=77.5946,
        waqi_keyword="bangalore"
    ),
    CityMetadata(
        id="hyderabad",
        name="Hyderabad",
        state="Telangana",
        latitude=17.3850,
        longitude=78.4867,
        waqi_keyword="hyderabad"
    ),
    CityMetadata(
        id="kolkata",
        name="Kolkata",
        state="West Bengal",
        latitude=22.5726,
        longitude=88.3639,
        waqi_keyword="kolkata"
    ),
    CityMetadata(
        id="chennai",
        name="Chennai",
        state="Tamil Nadu",
        latitude=13.0827,
        longitude=80.2707,
        waqi_keyword="chennai"
    ),
]


class AirQualityDataManager:
    """
    Orchestrates the 3-Tier Multi-Provider Pipeline:
    Tier 1: WAQI Ground Station (CPCB/PCB) -> OpenAQ v3 Secondary
    Tier 2: Open-Meteo CAMS Atmospheric Model
    Tier 3: Graceful Unavailable / Stale State
    Includes in-memory TTL caching and strict provenance tagging.
    """

    def __init__(self):
        self.waqi_provider = WAQIProvider()
        self.openaq_provider = OpenAQProvider()
        self.open_meteo_provider = OpenMeteoProvider()
        # In-memory observation cache: key -> (NormalizedAirObservation, cached_timestamp)
        self._cache: Dict[str, Tuple[NormalizedAirObservation, datetime]] = {}

    def get_supported_cities(self) -> List[CityMetadata]:
        return SUPPORTED_CITIES

    def _find_city(self, city_name_or_id: str) -> Optional[CityMetadata]:
        needle = city_name_or_id.lower().strip()
        for c in SUPPORTED_CITIES:
            if c.id == needle or c.name.lower() == needle:
                return c
        return None

    async def get_air_quality(
        self,
        city_identifier: str,
        station_id: Optional[str] = None
    ) -> NormalizedAirObservation:
        city_meta = self._find_city(city_identifier)
        if not city_meta:
            # Unsupported city -> return clear unavailable state
            now_utc = datetime.now(timezone.utc)
            return NormalizedAirObservation(
                city=city_identifier,
                locality_or_station=None,
                station_distance_km=None,
                source_type="unavailable",
                data_provider="None",
                observed_at=now_utc,
                fetched_at=now_utc,
                data_status="unavailable",
                confidence_score="unverified",
                index_type="unavailable",
                index_value=None,
                index_category="Unavailable",
                methodology_disclosure=f"City '{city_identifier}' is not currently configured for monitoring.",
            )

        cache_key = f"{city_meta.id}_{station_id or 'default'}"
        now = datetime.now(timezone.utc)

        # 1. Check in-memory cache
        if cache_key in self._cache:
            obs, cached_time = self._cache[cache_key]
            cache_age_seconds = (now - cached_time).total_seconds()
            if cache_age_seconds <= settings.AIR_DATA_CACHE_TTL_SECONDS:
                return obs

        # 2. Tier 1: Try WAQI (Ground Station Telemetry)
        waqi_obs = await self.waqi_provider.get_air_quality(
            city=city_meta.name,
            latitude=city_meta.latitude,
            longitude=city_meta.longitude,
            station_id=station_id or city_meta.waqi_keyword
        )
        if waqi_obs and waqi_obs.data_status == "live":
            self._cache[cache_key] = (waqi_obs, now)
            return waqi_obs

        # 3. Tier 1 (Secondary): Try OpenAQ v3
        openaq_obs = await self.openaq_provider.get_air_quality(
            city=city_meta.name,
            latitude=city_meta.latitude,
            longitude=city_meta.longitude,
            station_id=station_id
        )
        if openaq_obs and openaq_obs.data_status == "live":
            self._cache[cache_key] = (openaq_obs, now)
            return openaq_obs

        # 4. If WAQI returned stale data, we can keep it as a fallback option
        stale_ground_obs = waqi_obs if (waqi_obs and waqi_obs.data_status == "stale") else None

        # 5. Tier 2: Try Open-Meteo CAMS (Atmospheric Model Fallback)
        model_obs = await self.open_meteo_provider.get_air_quality(
            city=city_meta.name,
            latitude=city_meta.latitude,
            longitude=city_meta.longitude
        )
        if model_obs:
            self._cache[cache_key] = (model_obs, now)
            return model_obs

        # 6. Fallback to stale ground data if model also fails
        if stale_ground_obs:
            self._cache[cache_key] = (stale_ground_obs, now)
            return stale_ground_obs

        # 7. Check if old cached data exists (under 24h old)
        if cache_key in self._cache:
            old_obs, old_time = self._cache[cache_key]
            if (now - old_time).total_seconds() <= 86400:
                old_obs.source_type = "stale_cache"
                old_obs.data_status = "stale"
                old_obs.confidence_score = "low"
                old_obs.methodology_disclosure += " (Serving historical cache; live network telemetry unavailable)."
                return old_obs

        # 8. Tier 3: Genuine Unavailable State (Never fabricate!)
        return NormalizedAirObservation(
            city=city_meta.name,
            locality_or_station=None,
            station_distance_km=None,
            source_type="unavailable",
            data_provider="None",
            observed_at=now,
            fetched_at=now,
            data_status="unavailable",
            confidence_score="unverified",
            index_type="unavailable",
            index_value=None,
            index_category="Unavailable",
            methodology_disclosure="No active ground monitoring stations or atmospheric models responded for this location.",
        )


data_manager = AirQualityDataManager()
