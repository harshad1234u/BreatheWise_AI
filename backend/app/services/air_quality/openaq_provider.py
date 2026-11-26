import math
import httpx
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from app.core.config import settings
from app.core.http_client import acquire_http_client
from app.schemas.air_quality import (
    NormalizedAirObservation,
    PollutantConcentration,
)
from app.services.air_quality.base import AirQualityProvider
from app.services.air_quality.freshness import evaluate_observation_freshness
from app.services.cpcb_calculator import evaluate_naqi_from_concentrations

_PARAM_ALIASES: Dict[str, str] = {
    "pm25": "pm25",
    "pm2.5": "pm25",
    "pm2_5": "pm25",
    "pm10": "pm10",
    "no2": "no2",
    "so2": "so2",
    "co": "co",
    "o3": "o3",
    "nh3": "nh3",
    "pb": "pb",
}

# Standard molar masses (g/mol) at 25°C, 1 atm (24.45 L/mol molar volume) for CPCB gas conversions.
_GAS_MOLAR_MASS: Dict[str, float] = {
    "no2": 46.0055,
    "so2": 64.066,
    "co": 28.01,
    "o3": 48.00,
    "nh3": 17.031,
}

_PARTICULATE_PARAMS = {"pm25", "pm10", "pb"}
_UG_M3_UNITS = {"µg/m³", "µg/m3", "ug/m³", "ug/m3", "mcg/m³", "mcg/m3"}
_MG_M3_UNITS = {"mg/m³", "mg/m3"}


def normalize_openaq_measurement(
    param: str, raw_value: Any, raw_unit: Optional[str]
) -> Optional[Tuple[float, str, str, bool]]:
    """
    Validates numeric value and normalizes supported OpenAQ concentration units to CPCB units:
    - PM2.5, PM10, NO2, SO2, O3, NH3, Pb -> µg/m³
    - CO -> mg/m³
    Returns (value, normalized_unit, original_unit, is_thermodynamic_approximation) or None.
    ppb/ppm conversions use 25°C, 1 atm (molar volume 24.45 L/mol) and set is_converted=True.
    """
    if raw_value is None or isinstance(raw_value, bool):
        return None
    try:
        val = float(raw_value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(val) or val < 0.0:
        return None

    if not raw_unit or not isinstance(raw_unit, str) or not raw_unit.strip():
        return None
    orig_unit = raw_unit.strip()
    unit_key = orig_unit.lower().replace("μ", "µ").replace(" ", "")

    if param in _PARTICULATE_PARAMS:
        if unit_key in _UG_M3_UNITS:
            return round(val, 4), "µg/m³", orig_unit, False
        if unit_key in _MG_M3_UNITS:
            return round(val * 1000.0, 4), "µg/m³", orig_unit, False
        return None

    molar_mass = _GAS_MOLAR_MASS.get(param)
    if molar_mass is None:
        return None

    if param == "co":
        if unit_key in _MG_M3_UNITS:
            return round(val, 4), "mg/m³", orig_unit, False
        if unit_key in _UG_M3_UNITS:
            return round(val / 1000.0, 4), "mg/m³", orig_unit, False
        if unit_key == "ppm":
            return round(val * (molar_mass / 24.45), 4), "mg/m³", orig_unit, True
        if unit_key == "ppb":
            return round((val / 1000.0) * (molar_mass / 24.45), 4), "mg/m³", orig_unit, True
        return None

    if unit_key in _UG_M3_UNITS:
        return round(val, 4), "µg/m³", orig_unit, False
    if unit_key in _MG_M3_UNITS:
        return round(val * 1000.0, 4), "µg/m³", orig_unit, False
    if unit_key == "ppb":
        return round(val * (molar_mass / 24.45), 4), "µg/m³", orig_unit, True
    if unit_key == "ppm":
        return round(val * 1000.0 * (molar_mass / 24.45), 4), "µg/m³", orig_unit, True
    return None


def _extract_measurement_timestamp(item: Dict[str, Any]) -> Optional[str]:
    dt_val = item.get("datetime")
    if isinstance(dt_val, dict):
        utc_ts = dt_val.get("utc")
        if isinstance(utc_ts, str) and utc_ts.strip():
            return utc_ts
        local_ts = dt_val.get("local")
        if isinstance(local_ts, str) and local_ts.strip():
            return local_ts
        return None
    if isinstance(dt_val, str) and dt_val.strip():
        return dt_val
    return None


def _build_sensor_param_map(location: Dict[str, Any]) -> Dict[Any, Dict[str, Any]]:
    sensors = location.get("sensors")
    if not isinstance(sensors, list):
        return {}
    mapping: Dict[Any, Dict[str, Any]] = {}
    for sensor in sensors:
        if isinstance(sensor, dict) and sensor.get("id") is not None:
            param_info = sensor.get("parameter")
            if isinstance(param_info, dict):
                mapping[sensor["id"]] = param_info
    return mapping


class OpenAQProvider(AirQualityProvider):
    """
    Tier 1 Secondary: OpenAQ v3 API Provider.
    Queries global open ground monitoring stations as a secondary ground-truth backup.
    """

    def __init__(self, api_key: Optional[str] = None, http_client: Optional[httpx.AsyncClient] = None):
        self.api_key = api_key if api_key is not None else settings.OPENAQ_API_KEY
        self.base_url = "https://api.openaq.org/v3"
        self.http_client = http_client

    async def get_air_quality(
        self,
        city: str,
        latitude: float,
        longitude: float,
        station_id: Optional[str] = None
    ) -> Optional[NormalizedAirObservation]:
        if not self.api_key:
            return None

        headers = {"X-API-Key": self.api_key}

        try:
            async with acquire_http_client(
                injected_client=self.http_client, timeout=4.0, client_factory=httpx.AsyncClient
            ) as client:
                # Find nearest location within 25km
                search_url = f"{self.base_url}/locations?coordinates={latitude},{longitude}&radius=25000&limit=1"
                resp = await client.get(search_url, headers=headers, timeout=4.0)
                if resp.status_code != 200:
                    return None

                body = resp.json()
                if not isinstance(body, dict):
                    return None
                results = body.get("results")
                if not isinstance(results, list) or not results:
                    return None

                location = results[0]
                if not isinstance(location, dict):
                    return None
                loc_id = location.get("id")
                if loc_id is None:
                    return None

                raw_name = location.get("name")
                station_name = (
                    raw_name.strip() if isinstance(raw_name, str) and raw_name.strip() else f"{city} OpenAQ Monitor"
                )
                raw_dist = location.get("distance")
                station_distance_km: Optional[float] = None
                if (
                    raw_dist is not None
                    and not isinstance(raw_dist, bool)
                    and isinstance(raw_dist, (int, float))
                    and math.isfinite(float(raw_dist))
                    and float(raw_dist) >= 0.0
                ):
                    station_distance_km = round(float(raw_dist) / 1000.0, 2)

                sensor_map = _build_sensor_param_map(location)

                # Get latest measurements for this location
                latest_url = f"{self.base_url}/locations/{loc_id}/latest"
                latest_resp = await client.get(latest_url, headers=headers, timeout=4.0)
                if latest_resp.status_code != 200:
                    return None

                latest_body = latest_resp.json()
                if not isinstance(latest_body, dict):
                    return None
                measurements = latest_body.get("results")
                if not isinstance(measurements, list) or not measurements:
                    return None

                fetch_now = datetime.now(timezone.utc)
                pollutants: Dict[str, PollutantConcentration] = {}
                valid_timestamps = []
                converted_params = []

                for m in measurements:
                    if not isinstance(m, dict):
                        continue
                    param_obj = m.get("parameter") if isinstance(m.get("parameter"), dict) else None
                    if param_obj is None and m.get("sensorsId") in sensor_map:
                        param_obj = sensor_map[m["sensorsId"]]
                    if not isinstance(param_obj, dict):
                        continue

                    raw_param_name = param_obj.get("name")
                    if not isinstance(raw_param_name, str):
                        continue
                    canonical_param = _PARAM_ALIASES.get(raw_param_name.strip().lower())
                    if canonical_param is None:
                        continue

                    ts_str = _extract_measurement_timestamp(m)
                    parsed_obs_dt, ts_status, _ = evaluate_observation_freshness(ts_str, now_utc=fetch_now)
                    if parsed_obs_dt is None or ts_status not in ("live", "stale"):
                        continue

                    normalized = normalize_openaq_measurement(
                        canonical_param, m.get("value"), param_obj.get("units")
                    )
                    if normalized is None:
                        continue

                    norm_val, norm_unit, orig_unit, is_converted = normalized
                    pollutants[canonical_param] = PollutantConcentration(
                        value=norm_val,
                        unit=norm_unit,
                        averaging_period_hours=1,
                        source_unit=orig_unit,
                        is_converted=is_converted,
                    )
                    if is_converted and canonical_param.upper() not in converted_params:
                        converted_params.append(canonical_param.upper())
                    valid_timestamps.append(parsed_obs_dt)

                if not pollutants or not valid_timestamps:
                    return None

                observed_at = max(valid_timestamps)
                _, data_status, freshness_note = evaluate_observation_freshness(
                    observed_at.isoformat(), now_utc=fetch_now
                )
                if data_status not in ("live", "stale"):
                    return None

                index_val, category, index_type, disclosure = evaluate_naqi_from_concentrations(
                    pollutants, has_full_24h_data=False
                )
                if converted_params:
                    disclosure = (
                        f"{disclosure} Gas concentration ({', '.join(converted_params)}) converted from ppb/ppm "
                        f"using an assumed temperature of 25°C and pressure of 1 atmosphere (molar volume 24.45 L/mol). "
                        f"This is a standard-condition approximation, not a direct gravimetric measurement."
                    )
                confidence_score = "high" if data_status == "live" else "moderate"

                return NormalizedAirObservation(
                    city=city,
                    locality_or_station=station_name,
                    station_distance_km=station_distance_km,
                    source_type="ground_station",
                    data_provider="OpenAQ Ground Telemetry",
                    observed_at=observed_at,
                    fetched_at=fetch_now,
                    data_status=data_status,
                    freshness_note=freshness_note,
                    confidence_score=confidence_score,
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
