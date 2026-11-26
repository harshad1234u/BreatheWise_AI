import asyncio
from collections import OrderedDict
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple
import httpx

from app.core.config import settings
from app.schemas.air_quality import NormalizedAirObservation
from app.schemas.map import MapSummary, PollutantMapResponse, StationMapPoint
from app.services.air_quality.city_catalog import city_catalog
from app.services.air_quality.freshness import (
    evaluate_observation_freshness,
    map_us_epa_aqi_to_display_category,
)
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
    Provides spatial pollutant distributions across Pan-India monitoring networks.
    Distinguishes measurement types explicitly (`raw_concentration`, `provider_index`,
    `model_estimate`, `unavailable`), uses strict UTC/IST observation freshness,
    and caches raw city-scoped snapshots with bounded LRU/TTL storage & request coalescing.
    """

    def __init__(self, max_cached_cities: int = 48, cache_ttl_seconds: int = 600):
        self.waqi_token = settings.WAQI_API_TOKEN
        self.open_meteo_provider = OpenMeteoProvider()
        self._city_cache: OrderedDict[str, Tuple[datetime, Dict[str, Any]]] = OrderedDict()
        self._in_flight: Dict[str, asyncio.Task] = {}
        self.max_cached_cities = max_cached_cities
        self.cache_ttl_seconds = cache_ttl_seconds

    def clear_cache(self) -> None:
        self._city_cache.clear()
        self._in_flight.clear()

    def _find_city(self, city_name_or_id: str):
        return city_catalog.find_city(city_name_or_id)

    def _get_bounds_for_city(self, city_meta) -> Tuple[float, float, float, float]:
        if city_meta.id in CITY_BOUNDS:
            return CITY_BOUNDS[city_meta.id]
        # ~28 km half-width bounding box for dynamic Pan-India station discovery
        return (
            round(city_meta.latitude - 0.25, 4),
            round(city_meta.longitude - 0.25, 4),
            round(city_meta.latitude + 0.25, 4),
            round(city_meta.longitude + 0.25, 4),
        )

    async def _fetch_raw_city_snapshot(self, city_meta) -> Dict[str, Any]:
        now_utc = datetime.now(timezone.utc)
        raw_stations: List[Dict[str, Any]] = []
        bounds = self._get_bounds_for_city(city_meta)

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
                        station_list = b_data.get("data", []) if isinstance(b_data, dict) else []
                        selected_stations = [
                            s for s in station_list if isinstance(s, dict) and s.get("lat") is not None and s.get("lon") is not None
                        ][:14]

                        feed_tasks = [
                            client.get(
                                f"https://api.waqi.info/feed/@{s['uid']}/?token={self.waqi_token}",
                                timeout=4.0,
                            )
                            for s in selected_stations
                            if "uid" in s
                        ]
                        feed_results = await asyncio.gather(*feed_tasks, return_exceptions=True)

                        seen_ids = set()
                        for s_meta, f_res in zip(selected_stations, feed_results):
                            if isinstance(f_res, Exception) or f_res.status_code != 200:
                                continue
                            f_data = f_res.json()
                            if not isinstance(f_data, dict) or f_data.get("status") != "ok" or not f_data.get("data"):
                                continue

                            payload = f_data["data"]
                            station_id = f"station_{s_meta.get('uid', len(raw_stations))}"
                            if station_id in seen_ids:
                                continue
                            seen_ids.add(station_id)

                            station_name = payload.get("city", {}).get("name") or s_meta.get(
                                "station", {}
                            ).get("name", "Ground Monitoring Station")
                            geo = payload.get("city", {}).get("geo", [])
                            try:
                                lat = float(geo[0] if len(geo) > 0 and geo[0] is not None else s_meta.get("lat"))
                                lng = float(geo[1] if len(geo) > 1 and geo[1] is not None else s_meta.get("lon"))
                            except (TypeError, ValueError):
                                continue

                            time_iso = payload.get("time", {}).get("iso") if isinstance(payload.get("time"), dict) else None
                            attributions = payload.get("attributions", [])
                            attr_names = [a.get("name", "") for a in attributions if isinstance(a, dict) and a.get("name")]
                            provider_label = "WAQI Provider Feed"
                            if any("CPCB" in a for a in attr_names):
                                provider_label = "WAQI Feed (Station Network: CPCB/SPCB)"

                            raw_stations.append(
                                {
                                    "station_id": station_id,
                                    "station_name": station_name,
                                    "latitude": lat,
                                    "longitude": lng,
                                    "time_iso": time_iso,
                                    "data_provider": provider_label,
                                    "source_type": "ground_station",
                                    "iaqi": payload.get("iaqi", {}) if isinstance(payload.get("iaqi"), dict) else {},
                                }
                            )
            except Exception as e:
                logger.warning(f"Map service error querying WAQI bounds for {city_meta.name}: {e}")

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
                logger.warning(f"Atmospheric model fallback failed for {city_meta.name}: {e}")

        city_catalog.record_observed_availability(
            city_meta.id,
            has_ground=bool(raw_stations),
            has_model=bool(model_obs) or True,
        )

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
            del self._city_cache[city_meta.id]

        in_flight = self._in_flight.get(city_meta.id)
        if in_flight is None or in_flight.done():
            in_flight = asyncio.create_task(self._fetch_raw_city_snapshot(city_meta))
            self._in_flight[city_meta.id] = in_flight

        try:
            snapshot = await in_flight
        finally:
            if self._in_flight.get(city_meta.id) is in_flight:
                self._in_flight.pop(city_meta.id, None)

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
                    measurement_mode="unavailable",
                    data_provenance_note=f"City '{city_identifier}' is not supported for monitoring.",
                ),
            )

        snapshot = await self._get_or_fetch_city_snapshot(city_meta)
        stations_points: List[StationMapPoint] = []

        for raw in snapshot.get("ground_stations", []):
            obs_time, freshness, freshness_reason = evaluate_observation_freshness(
                raw.get("time_iso"), now_utc=now_utc
            )
            iaqi = raw.get("iaqi", {})
            raw_entry = iaqi.get(pollutant_key)

            provider_idx: Optional[float] = None
            provider_idx_cat: Optional[str] = None
            m_type = "unavailable"
            unavail_reason: Optional[str] = freshness_reason

            if isinstance(raw_entry, dict) and raw_entry.get("v") is not None:
                try:
                    parsed_idx = float(raw_entry["v"])
                    if parsed_idx >= 0:
                        if freshness == "expired":
                            m_type = "unavailable"
                            unavail_reason = freshness_reason or "Observation expired (>24h old)"
                        else:
                            provider_idx = round(parsed_idx, 1)
                            provider_idx_cat = map_us_epa_aqi_to_display_category(provider_idx)
                            m_type = "provider_index"
                            unavail_reason = (
                                "Raw concentration not provided by WAQI; displaying WAQI US-EPA sub-index"
                            )
                    else:
                        unavail_reason = f"Negative provider value rejected for {pollutant_key.upper()}"
                except (TypeError, ValueError):
                    unavail_reason = f"Non-numeric provider value for {pollutant_key.upper()}"
            else:
                unavail_reason = unavail_reason or f"Pollutant {pollutant_key.upper()} not reported by this WAQI station"

            conf = (
                "high"
                if (freshness == "live" and m_type == "provider_index")
                else ("moderate" if freshness == "stale" and m_type == "provider_index" else "low")
            )

            stations_points.append(
                StationMapPoint(
                    station_id=raw["station_id"],
                    station_name=raw["station_name"],
                    latitude=raw["latitude"],
                    longitude=raw["longitude"],
                    measurement_type=m_type,
                    concentration=None,
                    cpcb_sub_index=None,
                    sub_index_category="Unavailable",
                    provider_index=provider_idx,
                    provider_index_name="WAQI US-EPA AQI" if provider_idx is not None else None,
                    provider_index_category=provider_idx_cat,
                    unavailable_reason=unavail_reason,
                    observed_at=obs_time,
                    data_provider=raw["data_provider"],
                    source_type=raw["source_type"],
                    freshness_status=freshness,
                    quality_confidence=conf,
                )
            )

        model_obs: Optional[NormalizedAirObservation] = snapshot.get("model_observation")
        if not stations_points and model_obs is not None:
            conc_val = None
            sub_idx = None
            category = "Unavailable"
            m_type = "unavailable"
            unavail_reason = f"Model estimate unavailable for {pollutant_key.upper()}"
            pol_attr = getattr(model_obs, pollutant_key, None)
            if pol_attr and pol_attr.value is not None:
                conc_val = float(pol_attr.value)
                sub_idx = calculate_sub_index(pollutant_key, conc_val)
                category = get_aqi_category(sub_idx)
                m_type = "model_estimate"
                unavail_reason = None

            stations_points.append(
                StationMapPoint(
                    station_id=f"model_{city_meta.id}_center",
                    station_name=f"{city_meta.name} Regional Grid (Open-Meteo CAMS)",
                    latitude=city_meta.latitude,
                    longitude=city_meta.longitude,
                    measurement_type=m_type,
                    concentration=conc_val,
                    cpcb_sub_index=sub_idx,
                    sub_index_category=category,
                    provider_index=None,
                    provider_index_name=None,
                    provider_index_category=None,
                    unavailable_reason=unavail_reason,
                    observed_at=model_obs.observed_at,
                    data_provider="Open-Meteo CAMS (Atmospheric Model)",
                    source_type="atmospheric_model",
                    freshness_status="live",
                    quality_confidence="moderate",
                )
            )

        conc_pts = [
            s for s in stations_points
            if s.concentration is not None and s.measurement_type in ("raw_concentration", "cpcb_sub_index")
        ]
        idx_pts = [
            s for s in stations_points
            if s.provider_index is not None and s.measurement_type == "provider_index"
        ]
        model_pts = [
            s for s in stations_points
            if s.concentration is not None and s.measurement_type == "model_estimate"
        ]

        active_types = sum(1 for grp in (conc_pts, idx_pts, model_pts) if grp)
        if active_types > 1:
            mode = "mixed"
        elif conc_pts:
            mode = "raw_concentration"
        elif idx_pts:
            mode = "provider_index"
        elif model_pts:
            mode = "model_estimate"
        else:
            mode = "unavailable"

        # Never combine raw concentration and model estimates unless clearly same concentration unit;
        # never mix provider_index into concentration stats.
        conc_values = [s.concentration for s in (conc_pts or model_pts) if s.concentration is not None]
        idx_values = [s.provider_index for s in idx_pts if s.provider_index is not None]
        reporting_count = len(conc_pts) + len(idx_pts) + len(model_pts)

        if mode == "provider_index":
            provenance_note = (
                f"Displaying {len(idx_pts)} WAQI ground stations reporting normalized US-EPA AQI sub-indices "
                f"for {meta['name']}. Raw {meta['unit']} concentrations and CPCB concentration sub-indices are "
                f"marked unavailable rather than converted from index values."
            )
        elif mode == "model_estimate":
            provenance_note = (
                f"No active ground stations responded for {city_meta.name}. Displaying Open-Meteo CAMS "
                f"regional atmospheric model estimate ({meta['name']} in {meta['unit']}) with indicative CPCB sub-index."
            )
        elif mode == "raw_concentration":
            provenance_note = (
                f"Displaying ground monitoring station concentrations for {meta['name']} ({meta['unit']})."
            )
        else:
            provenance_note = (
                f"No live or usable {meta['name']} measurements were reported for {city_meta.name}. "
                "Missing readings remain strictly marked unavailable."
            )

        summary = MapSummary(
            total_stations=len(stations_points),
            reporting_stations=reporting_count,
            measurement_mode=mode,
            concentration_stations=len(conc_pts),
            provider_index_stations=len(idx_pts),
            model_stations=len(model_pts),
            min_concentration=min(conc_values) if conc_values else None,
            max_concentration=max(conc_values) if conc_values else None,
            avg_concentration=round(sum(conc_values) / len(conc_values), 1) if conc_values else None,
            min_provider_index=min(idx_values) if idx_values else None,
            max_provider_index=max(idx_values) if idx_values else None,
            avg_provider_index=round(sum(idx_values) / len(idx_values), 1) if idx_values else None,
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
