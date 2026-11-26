import asyncio
from collections import OrderedDict
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple
import httpx

from app.core.config import settings
from app.schemas.air_quality import NormalizedAirObservation
from app.schemas.map import MapSummary, PollutantMapResponse, StationMapPoint
from app.services.air_quality.data_manager import SUPPORTED_CITIES
from app.services.air_quality.open_meteo_provider import OpenMeteoProvider
from app.services.cpcb_calculator import calculate_sub_index, get_aqi_category

logger = logging.getLogger(__name__)

CITY_BOUNDS: Dict[str, Tuple[float, float, float, float]] = {
    "delhi": (28.30, 76.85, 28.90, 77.45),
    "mumbai": (18.85, 72.75, 19.35, 73.15),
    "bengaluru": (12.75, 77.40, 13.20, 77.80),
    "hyderabad": (17.20, 78.25, 17.60, 78.65),
    "kolkata": (22.35, 88.20, 22.80, 88.55),
    "chennai": (12.85, 80.05, 13.30, 80.35),
}

POLLUTANT_META: Dict[str, Dict[str, Any]] = {
    "pm25": {"name": "PM2.5 (Fine Particulates)", "unit": "µg/m³", "hours": 24},
    "pm10": {"name": "PM10 (Coarse Particulates)", "unit": "µg/m³", "hours": 24},
    "no2": {"name": "NO2 (Nitrogen Dioxide)", "unit": "µg/m³", "hours": 24},
    "so2": {"name": "SO2 (Sulfur Dioxide)", "unit": "µg/m³", "hours": 24},
    "o3": {"name": "O3 (Ground Ozone)", "unit": "µg/m³", "hours": 8},
    "co": {"name": "CO (Carbon Monoxide)", "unit": "mg/m³", "hours": 8},
    "nh3": {"name": "NH3 (Ammonia)", "unit": "µg/m³", "hours": 24},
    "pb": {"name": "Pb (Lead)", "unit": "µg/m³", "hours": 24},
}


class MapService:
    """
    Provides spatial pollutant distributions across Indian metro monitoring networks.
    Caches raw city-scoped provider snapshots with bounded LRU/TTL storage and
    in-flight request coalescing so switching pollutant tabs reuses cached station
    data without duplicate WAQI API fetches.
    """

    def __init__(self, max_cached_cities: int = 32, cache_ttl_seconds: int = 600):
        self.waqi_token = settings.WAQI_API_TOKEN
        self.open_meteo_provider = OpenMeteoProvider()
        # Bounded city cache: city_id -> (cached_at, raw_snapshot_dict)
        self._city_cache: OrderedDict[str, Tuple[datetime, Dict[str, Any]]] = OrderedDict()
        self._in_flight: Dict[str, asyncio.Task] = {}
        self.max_cached_cities = max_cached_cities
        self.cache_ttl_seconds = cache_ttl_seconds

    def clear_cache(self) -> None:
        self._city_cache.clear()
        self._in_flight.clear()

    def _find_city(self, city_name_or_id: str):
        needle = city_name_or_id.lower().strip()
        for c in SUPPORTED_CITIES:
            if c.id == needle or c.name.lower() == needle:
                return c
        return None

    async def _fetch_raw_city_snapshot(self, city_meta) -> Dict[str, Any]:
        """
        Fetches raw monitoring station payloads for a city once (independent of selected pollutant),
        falling back to Open-Meteo CAMS atmospheric model if no ground stations respond.
        """
        now_utc = datetime.now(timezone.utc)
        raw_stations: List[Dict[str, Any]] = []
        bounds = CITY_BOUNDS.get(city_meta.id)

        if self.waqi_token and bounds:
            try:
                bounds_url = (
                    f"https://api.waqi.info/v2/map/bounds?"
                    f"latlng={bounds[0]},{bounds[1]},{bounds[2]},{bounds[3]}&token={self.waqi_token}"
                )
                async with httpx.AsyncClient(timeout=6.0) as client:
                    b_res = await client.get(bounds_url)
                    if b_res.status_code == 200:
                        b_data = b_res.json()
                        station_list = b_data.get("data", [])
                        selected_stations = station_list[:14]

                        feed_tasks = [
                            client.get(
                                f"https://api.waqi.info/feed/@{s['uid']}/?token={self.waqi_token}",
                                timeout=4.0,
                            )
                            for s in selected_stations
                            if "uid" in s
                        ]
                        feed_results = await asyncio.gather(*feed_tasks, return_exceptions=True)

                        for s_meta, f_res in zip(selected_stations, feed_results):
                            if isinstance(f_res, Exception) or f_res.status_code != 200:
                                continue
                            f_data = f_res.json()
                            if f_data.get("status") != "ok" or not f_data.get("data"):
                                continue

                            payload = f_data["data"]
                            station_name = payload.get("city", {}).get("name") or s_meta.get(
                                "station", {}
                            ).get("name", "CPCB Monitoring Station")
                            geo = payload.get("city", {}).get("geo", [])
                            lat = float(geo[0] if len(geo) > 0 and geo[0] is not None else s_meta.get("lat"))
                            lng = float(geo[1] if len(geo) > 1 and geo[1] is not None else s_meta.get("lon"))

                            time_iso = payload.get("time", {}).get("iso")
                            try:
                                obs_time = (
                                    datetime.fromisoformat(time_iso.replace("Z", "+00:00"))
                                    if time_iso
                                    else now_utc
                                )
                            except Exception:
                                obs_time = now_utc

                            raw_stations.append(
                                {
                                    "station_id": f"station_{s_meta.get('uid', len(raw_stations))}",
                                    "station_name": station_name,
                                    "latitude": lat,
                                    "longitude": lng,
                                    "observed_at": obs_time,
                                    "data_provider": "WAQI (Official CPCB Ground Feed)",
                                    "source_type": "ground_station",
                                    "iaqi": payload.get("iaqi", {}),
                                }
                            )
            except Exception as e:
                logger.warning(f"Map service error querying WAQI bounds: {e}")

        model_obs: Optional[NormalizedAirObservation] = None
        if not raw_stations:
            logger.info(f"No ground stations found for {city_meta.name}. Attempting atmospheric model fallback...")
            try:
                model_obs = await self.open_meteo_provider.get_air_quality(
                    city=city_meta.name,
                    latitude=city_meta.latitude,
                    longitude=city_meta.longitude,
                )
            except Exception as e:
                logger.warning(f"Atmospheric model fallback failed: {e}")

        return {
            "fetched_at": now_utc,
            "ground_stations": raw_stations,
            "model_observation": model_obs,
        }

    async def _get_or_fetch_city_snapshot(self, city_meta) -> Dict[str, Any]:
        now_utc = datetime.now(timezone.utc)
        cached = self._city_cache.get(city_meta.id)
        if cached is not None:
            cached_at, snapshot = cached
            if (now_utc - cached_at).total_seconds() <= self.cache_ttl_seconds:
                self._city_cache.move_to_end(city_meta.id)
                return snapshot
            # Expired entry: evict immediately so stale snapshots are never served as fresh
            del self._city_cache[city_meta.id]

        # Coalesce concurrent cache misses for the same city
        in_flight = self._in_flight.get(city_meta.id)
        if in_flight is None or in_flight.done():
            in_flight = asyncio.create_task(self._fetch_raw_city_snapshot(city_meta))
            self._in_flight[city_meta.id] = in_flight

        try:
            snapshot = await in_flight
        finally:
            if self._in_flight.get(city_meta.id) is in_flight:
                self._in_flight.pop(city_meta.id, None)

        # Store in bounded LRU cache (only if snapshot holds data or valid fallback check completed)
        self._city_cache[city_meta.id] = (datetime.now(timezone.utc), snapshot)
        self._city_cache.move_to_end(city_meta.id)
        while len(self._city_cache) > self.max_cached_cities:
            self._city_cache.popitem(last=False)

        return snapshot

    async def get_city_pollutant_map(
        self,
        city_identifier: str,
        pollutant: str = "pm25",
    ) -> PollutantMapResponse:
        pollutant_key = pollutant.lower().strip()
        if pollutant_key not in POLLUTANT_META:
            supported = ", ".join(POLLUTANT_META.keys())
            raise ValueError(f"Invalid pollutant parameter '{pollutant}'. Supported parameters: {supported}")

        meta = POLLUTANT_META[pollutant_key]
        city_meta = self._find_city(city_identifier)
        now_utc = datetime.now(timezone.utc)

        if not city_meta:
            return PollutantMapResponse(
                selected_city=city_identifier,
                city_center_lat=20.5937,
                city_center_lng=78.9629,
                selected_pollutant=pollutant_key,
                pollutant_name=meta["name"],
                unit=meta["unit"],
                stations=[],
                summary=MapSummary(
                    total_stations=0,
                    reporting_stations=0,
                    data_provenance_note=f"City '{city_identifier}' is not supported for monitoring.",
                ),
            )

        snapshot = await self._get_or_fetch_city_snapshot(city_meta)
        stations_points: List[StationMapPoint] = []

        for raw in snapshot.get("ground_stations", []):
            obs_time: datetime = raw["observed_at"]
            age_hours = (now_utc - obs_time.astimezone(timezone.utc)).total_seconds() / 3600.0
            freshness = "stale" if age_hours > settings.GROUND_DATA_FRESHNESS_HOURS else "live"

            # WAQI station feeds expose `iaqi[pollutant].v` as dimensionless US-EPA AQI
            # sub-indices, NOT raw µg/m³ or mg/m³ concentrations. Never label them as mass
            # concentrations or pass sub-indices through CPCB concentration breakpoints.
            stations_points.append(
                StationMapPoint(
                    station_id=raw["station_id"],
                    station_name=raw["station_name"],
                    latitude=raw["latitude"],
                    longitude=raw["longitude"],
                    concentration=None,
                    cpcb_sub_index=None,
                    sub_index_category="Unavailable",
                    observed_at=obs_time,
                    data_provider=raw["data_provider"],
                    source_type=raw["source_type"],
                    freshness_status=freshness,
                    quality_confidence="high" if freshness == "live" else "moderate",
                )
            )

        model_obs: Optional[NormalizedAirObservation] = snapshot.get("model_observation")
        if not stations_points and model_obs is not None:
            conc_val = None
            sub_idx = None
            category = "Unavailable"
            pol_attr = getattr(model_obs, pollutant_key, None)
            if pol_attr and pol_attr.value is not None:
                conc_val = float(pol_attr.value)
                sub_idx = calculate_sub_index(pollutant_key, conc_val)
                category = get_aqi_category(sub_idx)

            stations_points.append(
                StationMapPoint(
                    station_id=f"model_{city_meta.id}_center",
                    station_name=f"{city_meta.name} Center (Atmospheric Model Grid)",
                    latitude=city_meta.latitude,
                    longitude=city_meta.longitude,
                    concentration=conc_val,
                    cpcb_sub_index=sub_idx,
                    sub_index_category=category,
                    observed_at=model_obs.observed_at,
                    data_provider="Open-Meteo CAMS (Atmospheric Model)",
                    source_type="atmospheric_model",
                    freshness_status="live",
                    quality_confidence="moderate",
                )
            )

        reporting = [s for s in stations_points if s.concentration is not None]
        concs = [s.concentration for s in reporting]
        has_waqi_only = (
            bool(stations_points)
            and all(s.source_type == "ground_station" for s in stations_points)
            and not reporting
        )

        provenance_note = (
            (
                f"WAQI ground feeds report normalized US-EPA AQI sub-indices rather than raw {meta['unit']} "
                f"concentrations for {meta['name']}. Raw concentrations and CPCB sub-indices are marked "
                f"unavailable rather than converted from index values. Not an official CPCB pollution map."
            )
            if has_waqi_only
            else (
                f"Displaying real-time monitoring telemetry for {meta['name']} ({meta['unit']}). "
                "Not an official CPCB pollution map."
            )
        )

        summary = MapSummary(
            total_stations=len(stations_points),
            reporting_stations=len(reporting),
            min_concentration=min(concs) if concs else None,
            max_concentration=max(concs) if concs else None,
            avg_concentration=round(sum(concs) / len(concs), 1) if concs else None,
            data_provenance_note=provenance_note,
        )

        return PollutantMapResponse(
            selected_city=city_meta.name,
            city_center_lat=city_meta.latitude,
            city_center_lng=city_meta.longitude,
            selected_pollutant=pollutant_key,
            pollutant_name=meta["name"],
            unit=meta["unit"],
            stations=stations_points,
            summary=summary,
        )


map_service = MapService()
