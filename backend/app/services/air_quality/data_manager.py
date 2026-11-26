from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from app.core.config import settings
from app.schemas.air_quality import CityMetadata, NormalizedAirObservation
from app.services.air_quality.city_catalog import city_catalog
from app.services.air_quality.open_meteo_provider import OpenMeteoProvider
from app.services.air_quality.openaq_provider import OpenAQProvider
from app.services.air_quality.waqi_provider import WAQIProvider

SUPPORTED_CITIES: List[CityMetadata] = city_catalog.all_cities()


class AirQualityDataManager:
    """
    Orchestrates the 3-Tier Multi-Provider Pipeline across the Pan-India geographic catalog:
    Tier 1: WAQI Ground Station -> OpenAQ v3 Secondary
    Tier 2: Open-Meteo CAMS Atmospheric Model
    Tier 3: Graceful Unavailable / Stale State
    Includes in-memory TTL caching, strict provenance tagging, and observed coverage tracking.
    """

    def __init__(self):
        self.waqi_provider = WAQIProvider()
        self.openaq_provider = OpenAQProvider()
        self.open_meteo_provider = OpenMeteoProvider()
        self._cache: Dict[str, Tuple[NormalizedAirObservation, datetime]] = {}

    def get_supported_cities(
        self,
        q: Optional[str] = None,
        state: Optional[str] = None,
        region_type: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[CityMetadata]:
        return city_catalog.query(q=q, state=state, region_type=region_type, limit=limit, offset=offset)

    def _find_city(self, city_name_or_id: str) -> Optional[CityMetadata]:
        return city_catalog.find_city(city_name_or_id)

    async def get_air_quality(
        self,
        city_identifier: str,
        station_id: Optional[str] = None
    ) -> NormalizedAirObservation:
        city_meta = self._find_city(city_identifier)
        if not city_meta:
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
                methodology_disclosure=f"City '{city_identifier}' is not currently in the geographic catalog.",
            )

        cache_key = f"{city_meta.id}_{station_id or 'default'}"
        now = datetime.now(timezone.utc)

        if cache_key in self._cache:
            obs, cached_time = self._cache[cache_key]
            cache_age_seconds = (now - cached_time).total_seconds()
            if cache_age_seconds <= settings.AIR_DATA_CACHE_TTL_SECONDS:
                return obs

        # Tier 1: Try WAQI using geo coordinates for reliable Pan-India station discovery
        waqi_obs = await self.waqi_provider.get_air_quality(
            city=city_meta.name,
            latitude=city_meta.latitude,
            longitude=city_meta.longitude,
            station_id=station_id if (station_id and station_id.startswith("@")) else None,
        )
        if waqi_obs and waqi_obs.data_status == "live":
            city_catalog.record_observed_availability(city_meta.id, has_ground=True, has_model=True)
            self._cache[cache_key] = (waqi_obs, now)
            return waqi_obs

        # Tier 1 (Secondary): Try OpenAQ v3
        openaq_obs = await self.openaq_provider.get_air_quality(
            city=city_meta.name,
            latitude=city_meta.latitude,
            longitude=city_meta.longitude,
            station_id=station_id,
        )
        if openaq_obs and openaq_obs.data_status == "live":
            city_catalog.record_observed_availability(city_meta.id, has_ground=True, has_model=True)
            self._cache[cache_key] = (openaq_obs, now)
            return openaq_obs

        stale_ground_obs = waqi_obs if (waqi_obs and waqi_obs.data_status == "stale") else None

        # Tier 2: Try Open-Meteo CAMS (Atmospheric Model Fallback)
        model_obs = await self.open_meteo_provider.get_air_quality(
            city=city_meta.name,
            latitude=city_meta.latitude,
            longitude=city_meta.longitude,
        )
        if model_obs:
            city_catalog.record_observed_availability(
                city_meta.id, has_ground=bool(stale_ground_obs), has_model=True
            )
            self._cache[cache_key] = (model_obs, now)
            return model_obs

        if stale_ground_obs:
            city_catalog.record_observed_availability(city_meta.id, has_ground=True, has_model=False)
            self._cache[cache_key] = (stale_ground_obs, now)
            return stale_ground_obs

        if cache_key in self._cache:
            old_obs, old_time = self._cache[cache_key]
            if (now - old_time).total_seconds() <= 86400:
                old_obs.source_type = "stale_cache"
                old_obs.data_status = "stale"
                old_obs.confidence_score = "low"
                old_obs.methodology_disclosure += " (Serving historical cache; live network telemetry unavailable)."
                return old_obs

        city_catalog.record_observed_availability(city_meta.id, has_ground=False, has_model=False)
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
