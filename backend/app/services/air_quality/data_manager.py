import asyncio
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from app.core.config import settings
from app.schemas.air_quality import CityMetadata, NormalizedAirObservation, RegionType
from app.services.air_quality.cache_utils import run_coalesced, set_bounded_lru
from app.services.air_quality.city_catalog import city_catalog
from app.services.air_quality.open_meteo_provider import OpenMeteoProvider
from app.services.air_quality.openaq_provider import OpenAQProvider
from app.services.air_quality.waqi_provider import WAQIProvider

SUPPORTED_CITIES: List[CityMetadata] = city_catalog.all_cities()
_STALE_CACHE_NOTE = " (Serving historical cache; live network telemetry unavailable)."


class AirQualityDataManager:
    """
    Orchestrates the 3-Tier Multi-Provider Pipeline across the Pan-India geographic catalog:
    Tier 1: WAQI Ground Station -> OpenAQ v3 Secondary
    Tier 2: Open-Meteo CAMS Atmospheric Model
    Tier 3: Graceful Unavailable / Stale State
    Includes bounded LRU/TTL caching, per-key concurrent coalescing, immutable cache
    reads, and strict provenance tagging.
    """

    def __init__(
        self,
        max_cache_entries: int = 128,
        cache_ttl_seconds: Optional[int] = None,
    ):
        self.waqi_provider = WAQIProvider()
        self.openaq_provider = OpenAQProvider()
        self.open_meteo_provider = OpenMeteoProvider()
        self.max_cache_entries = max_cache_entries
        self._cache_ttl_override = cache_ttl_seconds
        self._cache: OrderedDict[str, Tuple[NormalizedAirObservation, datetime]] = OrderedDict()
        self._in_flight: Dict[str, asyncio.Task] = {}

    def clear_cache(self) -> None:
        self._cache.clear()
        self._in_flight.clear()

    def _effective_ttl(self) -> int:
        if self._cache_ttl_override is not None:
            return self._cache_ttl_override
        return settings.AIR_DATA_CACHE_TTL_SECONDS

    def get_supported_cities(
        self,
        q: Optional[str] = None,
        state: Optional[str] = None,
        region_type: Optional[RegionType] = None,
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
        ttl_seconds = self._effective_ttl()

        prior_entry = self._cache.get(cache_key)
        if prior_entry is not None:
            obs, cached_time = prior_entry
            if (now - cached_time).total_seconds() <= ttl_seconds:
                self._cache.move_to_end(cache_key)
                return obs.model_copy(deep=True)

        async def _fetch_live_or_fallback() -> NormalizedAirObservation:
            fetch_now = datetime.now(timezone.utc)

            # Tier 1: Try WAQI using geo coordinates for reliable Pan-India station discovery
            waqi_obs = await self.waqi_provider.get_air_quality(
                city=city_meta.name,
                latitude=city_meta.latitude,
                longitude=city_meta.longitude,
                station_id=station_id if (station_id and station_id.startswith("@")) else None,
            )
            if waqi_obs and waqi_obs.data_status == "live":
                set_bounded_lru(
                    self._cache, cache_key, (waqi_obs.model_copy(deep=True), fetch_now), self.max_cache_entries
                )
                return waqi_obs.model_copy(deep=True)

            # Tier 1 (Secondary): Try OpenAQ v3
            openaq_obs = await self.openaq_provider.get_air_quality(
                city=city_meta.name,
                latitude=city_meta.latitude,
                longitude=city_meta.longitude,
                station_id=station_id,
            )
            if openaq_obs and openaq_obs.data_status == "live":
                set_bounded_lru(
                    self._cache, cache_key, (openaq_obs.model_copy(deep=True), fetch_now), self.max_cache_entries
                )
                return openaq_obs.model_copy(deep=True)

            stale_ground_obs = (
                waqi_obs
                if (waqi_obs and waqi_obs.data_status == "stale")
                else (openaq_obs if (openaq_obs and openaq_obs.data_status == "stale") else None)
            )

            # Tier 2: Try Open-Meteo CAMS (Atmospheric Model Fallback)
            model_obs = await self.open_meteo_provider.get_air_quality(
                city=city_meta.name,
                latitude=city_meta.latitude,
                longitude=city_meta.longitude,
            )
            if model_obs and model_obs.data_status == "live":
                set_bounded_lru(
                    self._cache, cache_key, (model_obs.model_copy(deep=True), fetch_now), self.max_cache_entries
                )
                return model_obs.model_copy(deep=True)

            if stale_ground_obs:
                set_bounded_lru(
                    self._cache,
                    cache_key,
                    (stale_ground_obs.model_copy(deep=True), fetch_now),
                    self.max_cache_entries,
                )
                return stale_ground_obs.model_copy(deep=True)

            if model_obs and model_obs.data_status == "stale":
                set_bounded_lru(
                    self._cache, cache_key, (model_obs.model_copy(deep=True), fetch_now), self.max_cache_entries
                )
                return model_obs.model_copy(deep=True)

            hist_entry = self._cache.get(cache_key) or prior_entry
            if hist_entry is not None:
                old_obs, old_time = hist_entry
                if (fetch_now - old_time).total_seconds() <= 86400:
                    disclosure = old_obs.methodology_disclosure
                    if _STALE_CACHE_NOTE not in disclosure:
                        disclosure = disclosure + _STALE_CACHE_NOTE
                    return old_obs.model_copy(
                        deep=True,
                        update={
                            "source_type": "stale_cache",
                            "data_status": "stale",
                            "confidence_score": "low",
                            "methodology_disclosure": disclosure,
                        },
                    )

            return NormalizedAirObservation(
                city=city_meta.name,
                locality_or_station=None,
                station_distance_km=None,
                source_type="unavailable",
                data_provider="None",
                observed_at=fetch_now,
                fetched_at=fetch_now,
                data_status="unavailable",
                confidence_score="unverified",
                index_type="unavailable",
                index_value=None,
                index_category="Unavailable",
                methodology_disclosure="No active ground monitoring stations or atmospheric models responded for this location.",
            )

        return await run_coalesced(self._in_flight, cache_key, _fetch_live_or_fallback)


data_manager = AirQualityDataManager()
