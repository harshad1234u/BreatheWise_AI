import asyncio
from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional, Tuple
import httpx

from app.core.config import settings
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

POLLUTANT_META: Dict[str, Dict[str, any]] = {
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
    def __init__(self):
        self.waqi_token = settings.WAQI_API_TOKEN
        self.open_meteo_provider = OpenMeteoProvider()
        # Cache: key -> (PollutantMapResponse, cached_time)
        self._cache: Dict[str, Tuple[PollutantMapResponse, datetime]] = {}
        self.cache_ttl_seconds = 600  # 10 minutes

    def _find_city(self, city_name_or_id: str):
        needle = city_name_or_id.lower().strip()
        for c in SUPPORTED_CITIES:
            if c.id == needle or c.name.lower() == needle:
                return c
        return None

    async def get_city_pollutant_map(
        self,
        city_identifier: str,
        pollutant: str = "pm25"
    ) -> PollutantMapResponse:
        pollutant_key = pollutant.lower().strip()
        if pollutant_key not in POLLUTANT_META:
            supported = ", ".join(POLLUTANT_META.keys())
            raise ValueError(f"Invalid pollutant parameter '{pollutant}'. Supported parameters: {supported}")

        meta = POLLUTANT_META[pollutant_key]
        city_meta = self._find_city(city_identifier)
        now_utc = datetime.now(timezone.utc)

        if not city_meta:
            # Unsupported City
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
                    data_provenance_note=f"City '{city_identifier}' is not supported for monitoring."
                )
            )

        cache_key = f"{city_meta.id}_{pollutant_key}"
        if cache_key in self._cache:
            resp, cached_time = self._cache[cache_key]
            if (now_utc - cached_time).total_seconds() <= self.cache_ttl_seconds:
                return resp

        # Fetch live data from WAQI bounds
        stations_points: List[StationMapPoint] = []
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
                        raw_stations = b_data.get("data", [])
                        
                        # Limit to top 14 stations for responsive parallel loading
                        selected_stations = raw_stations[:14]
                        
                        feed_tasks = [
                            client.get(
                                f"https://api.waqi.info/feed/@{s['uid']}/?token={self.waqi_token}",
                                timeout=4.0
                            )
                            for s in selected_stations if "uid" in s
                        ]
                        
                        feed_results = await asyncio.gather(*feed_tasks, return_exceptions=True)

                        for s_meta, f_res in zip(selected_stations, feed_results):
                            if isinstance(f_res, Exception) or f_res.status_code != 200:
                                continue
                            f_data = f_res.json()
                            if f_data.get("status") != "ok" or not f_data.get("data"):
                                continue

                            payload = f_data["data"]
                            iaqi = payload.get("iaqi", {})
                            
                            station_name = payload.get("city", {}).get("name") or s_meta.get("station", {}).get("name", "CPCB Monitoring Station")
                            lat = float(payload.get("city", {}).get("geo", [s_meta.get("lat")])[0] or s_meta.get("lat"))
                            lng = float(payload.get("city", {}).get("geo", [0, s_meta.get("lon")])[1] or s_meta.get("lon"))

                            time_iso = payload.get("time", {}).get("iso")
                            try:
                                obs_time = datetime.fromisoformat(time_iso.replace("Z", "+00:00")) if time_iso else now_utc
                            except Exception:
                                obs_time = now_utc

                            age_hours = (now_utc - obs_time.astimezone(timezone.utc)).total_seconds() / 3600.0
                            freshness = "stale" if age_hours > settings.GROUND_DATA_FRESHNESS_HOURS else "live"

                            # WAQI station feeds expose `iaqi[pollutant].v` as dimensionless US-EPA AQI
                            # sub-indices, NOT raw µg/m³ or mg/m³ concentrations. Never label them as mass
                            # concentrations or pass sub-indices through CPCB concentration breakpoints.
                            conc_val = None
                            sub_idx = None
                            category = "Unavailable"

                            stations_points.append(
                                StationMapPoint(
                                    station_id=f"station_{s_meta.get('uid', len(stations_points))}",
                                    station_name=station_name,
                                    latitude=lat,
                                    longitude=lng,
                                    concentration=conc_val,
                                    cpcb_sub_index=sub_idx,
                                    sub_index_category=category,
                                    observed_at=obs_time,
                                    data_provider="WAQI (Official CPCB Ground Feed)",
                                    source_type="ground_station",
                                    freshness_status=freshness,
                                    quality_confidence="high" if freshness == "live" else "moderate",
                                )
                            )

            except Exception as e:
                logger.warning(f"Map service error querying WAQI bounds: {e}")

        # Fallback to atmospheric model if no ground stations reported
        if not stations_points:
            logger.info(f"No ground stations found for {city_meta.name}. Attempting atmospheric model fallback...")
            try:
                model_obs = await self.open_meteo_provider.get_air_quality(
                    city=city_meta.name,
                    latitude=city_meta.latitude,
                    longitude=city_meta.longitude
                )
                if model_obs:
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
            except Exception as e:
                logger.warning(f"Atmospheric model fallback failed: {e}")

        # Summary statistics
        reporting = [s for s in stations_points if s.concentration is not None]
        concs = [s.concentration for s in reporting]
        has_waqi_only = bool(stations_points) and all(s.source_type == "ground_station" for s in stations_points) and not reporting

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

        resp = PollutantMapResponse(
            selected_city=city_meta.name,
            city_center_lat=city_meta.latitude,
            city_center_lng=city_meta.longitude,
            selected_pollutant=pollutant_key,
            pollutant_name=meta["name"],
            unit=meta["unit"],
            stations=stations_points,
            summary=summary
        )

        self._cache[cache_key] = (resp, now_utc)
        return resp


map_service = MapService()
