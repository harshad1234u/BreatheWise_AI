import asyncio
import httpx
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from app.core.config import settings
from app.schemas.air_window import (
    AirWindowResponse,
    BestAirWindowPeriod,
    HourlyPollutantPoint,
)
from app.services.air_quality.city_catalog import city_catalog
from app.services.cpcb_calculator import calculate_sub_index, get_aqi_category


class AirWindowService:
    """
    Multi-pollutant comparative Best Air Window calculation engine.
    Analyzes Open-Meteo CAMS 48-hour atmospheric forecasts (PM2.5, PM10, O3, NO2, SO2, CO)
    to identify diurnal periods with comparatively lower relative pollutant exposure.
    
    IMPORTANT: Follows PRD v1.2 public-health safeguards:
    - Never uses 'Safe', 'Healthy', or 'Pollution-free' labels.
    - Uses 'Lowest Forecast Pollution Period', 'Comparatively Better Window', 'Higher Pollution Period'.
    - Interlocks with CPCB/MoHFW safety thresholds (disallows strenuous outdoor exercise in Very Poor/Severe bands).
    """

    def __init__(self):
        self.aq_base_url = "https://air-quality-api.open-meteo.com/v1/air-quality"
        self.weather_base_url = "https://api.open-meteo.com/v1/forecast"
        self._forecast_cache: Dict[str, Tuple[datetime, dict, dict]] = {}

    def _find_city(self, city_identifier: str):
        return city_catalog.find_city(city_identifier)

    def _determine_duration(self, activity: str, requested_duration: Optional[int]) -> int:
        if requested_duration and 1 <= requested_duration <= 3:
            return requested_duration
        
        act = activity.lower().strip()
        if any(kw in act for kw in ["run", "jog", "workout", "exercise", "cycle", "cycling"]):
            return 1
        elif any(kw in act for kw in ["walk", "commute", "school", "errand", "market"]):
            return 1
        elif any(kw in act for kw in ["ventilate", "window", "airing"]):
            return 1
        return 1

    async def calculate_best_window(
        self,
        city_identifier: str,
        activity: str = "general_outdoor",
        duration_hours: Optional[int] = None,
        is_vulnerable: bool = False,
    ) -> AirWindowResponse:
        city_meta = self._find_city(city_identifier)
        duration = self._determine_duration(activity, duration_hours)
        now_dt = datetime.now(timezone.utc)

        if not city_meta:
            return AirWindowResponse(
                city=city_identifier,
                activity=activity,
                duration_hours=duration,
                generated_at=now_dt,
                data_provenance_type="unavailable",
                confidence="unverified",
                status="unavailable",
                disclaimer="City not supported or recognized. Cannot generate atmospheric forecast.",
            )

        # Check cache for recent forecast data for this city
        aq_data = None
        weather_data = {}
        cached_entry = self._forecast_cache.get(city_meta.id)
        if cached_entry:
            cached_at, cached_aq, cached_weather = cached_entry
            if (now_dt - cached_at).total_seconds() < settings.AIR_DATA_CACHE_TTL_SECONDS:
                aq_data = cached_aq
                weather_data = cached_weather

        if aq_data is None:
            # Fetch CAMS Air Quality and Meteorological data in parallel
            aq_params = {
                "latitude": city_meta.latitude,
                "longitude": city_meta.longitude,
                "hourly": "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone",
                "forecast_days": 2,
                "timezone": "Asia/Kolkata",
            }
            weather_params = {
                "latitude": city_meta.latitude,
                "longitude": city_meta.longitude,
                "hourly": "wind_speed_10m",
                "forecast_days": 2,
                "timezone": "Asia/Kolkata",
            }

            try:
                async with httpx.AsyncClient(timeout=6.0) as client:
                    aq_task = client.get(self.aq_base_url, params=aq_params)
                    weather_task = client.get(self.weather_base_url, params=weather_params)
                    aq_resp, weather_resp = await asyncio.gather(aq_task, weather_task, return_exceptions=True)

                if isinstance(aq_resp, Exception) or aq_resp.status_code != 200:
                    return self._build_insufficient_response(city_meta.name, activity, duration, now_dt)

                aq_data = aq_resp.json()
                weather_data = weather_resp.json() if not isinstance(weather_resp, Exception) and weather_resp.status_code == 200 else {}
                self._forecast_cache[city_meta.id] = (now_dt, aq_data, weather_data)
            except Exception:
                return self._build_insufficient_response(city_meta.name, activity, duration, now_dt)

        hourly_aq = aq_data.get("hourly", {})
        times = hourly_aq.get("time", [])
        if not times:
            return self._build_insufficient_response(city_meta.name, activity, duration, now_dt)

        pm25_series = hourly_aq.get("pm2_5", [])
        pm10_series = hourly_aq.get("pm10", [])
        o3_series = hourly_aq.get("ozone", [])
        no2_series = hourly_aq.get("nitrogen_dioxide", [])
        so2_series = hourly_aq.get("sulphur_dioxide", [])
        co_series = hourly_aq.get("carbon_monoxide", [])

        hourly_weather = weather_data.get("hourly", {})
        wind_series = hourly_weather.get("wind_speed_10m", [])

        # Process hourly points
        hourly_points: List[HourlyPollutantPoint] = []
        for i, t_str in enumerate(times):
            # Parse human label e.g. "06:00" from "2026-11-24T06:00"
            hour_part = t_str.split("T")[-1] if "T" in t_str else t_str[-5:]
            if len(hour_part) > 5:
                hour_part = hour_part[:5]

            pm25_val = float(pm25_series[i]) if i < len(pm25_series) and pm25_series[i] is not None else None
            pm10_val = float(pm10_series[i]) if i < len(pm10_series) and pm10_series[i] is not None else None
            o3_val = float(o3_series[i]) if i < len(o3_series) and o3_series[i] is not None else None
            no2_val = float(no2_series[i]) if i < len(no2_series) and no2_series[i] is not None else None
            so2_val = float(so2_series[i]) if i < len(so2_series) and so2_series[i] is not None else None
            
            # CO: Open-Meteo returns µg/m³, convert to mg/m³ for CPCB scale
            co_val = None
            if i < len(co_series) and co_series[i] is not None:
                co_val = round(float(co_series[i]) / 1000.0, 2)

            wind_val = float(wind_series[i]) if i < len(wind_series) and wind_series[i] is not None else None

            # Calculate sub-indices across all available parameters
            sub_indices: Dict[str, float] = {}
            if pm25_val is not None:
                s = calculate_sub_index("pm25", pm25_val)
                if s is not None:
                    sub_indices["pm25"] = s
            if pm10_val is not None:
                s = calculate_sub_index("pm10", pm10_val)
                if s is not None:
                    sub_indices["pm10"] = s
            if o3_val is not None:
                s = calculate_sub_index("o3", o3_val)
                if s is not None:
                    sub_indices["o3"] = s
            if no2_val is not None:
                s = calculate_sub_index("no2", no2_val)
                if s is not None:
                    sub_indices["no2"] = s
            if so2_val is not None:
                s = calculate_sub_index("so2", so2_val)
                if s is not None:
                    sub_indices["so2"] = s
            if co_val is not None:
                s = calculate_sub_index("co", co_val)
                if s is not None:
                    sub_indices["co"] = s

            if not sub_indices:
                continue

            # Comparative score is max sub-index
            dominant_pol = max(sub_indices, key=sub_indices.get)
            comp_score = round(sub_indices[dominant_pol], 1)
            cat_label = get_aqi_category(comp_score)

            hourly_points.append(
                HourlyPollutantPoint(
                    timestamp=t_str,
                    hour_label=hour_part,
                    pm25=pm25_val,
                    pm10=pm10_val,
                    o3=o3_val,
                    no2=no2_val,
                    so2=so2_val,
                    co=co_val,
                    wind_speed=wind_val,
                    comparative_score=comp_score,
                    dominant_pollutant=dominant_pol,
                    category_label=cat_label,
                )
            )

        if len(hourly_points) < duration:
            return self._build_insufficient_response(city_meta.name, activity, duration, now_dt)

        # Sliding window calculation across the forecast horizon (next 24 hours evaluation)
        eval_horizon = min(len(hourly_points), 24)
        valid_windows = []

        for start_idx in range(0, eval_horizon - duration + 1):
            window_slice = hourly_points[start_idx : start_idx + duration]
            avg_score = round(sum(p.comparative_score for p in window_slice) / duration, 1)

            # Dominant pollutant across window
            pol_counts: Dict[str, int] = {}
            for p in window_slice:
                pol_counts[p.dominant_pollutant] = pol_counts.get(p.dominant_pollutant, 0) + 1
            win_dominant = max(pol_counts, key=pol_counts.get)

            start_p = window_slice[0]
            end_p = window_slice[-1]

            # Calculate end hour display (e.g. 06:00 + 1h = 07:00)
            end_label = self._calculate_end_label(end_p.hour_label)

            valid_windows.append({
                "start_idx": start_idx,
                "start_time": start_p.hour_label,
                "end_time": end_label,
                "start_iso": start_p.timestamp,
                "end_iso": end_p.timestamp,
                "avg_score": avg_score,
                "dominant_pollutant": win_dominant,
            })

        if not valid_windows:
            return self._build_insufficient_response(city_meta.name, activity, duration, now_dt)

        # Sort windows by average score
        sorted_by_score = sorted(valid_windows, key=lambda w: w["avg_score"])
        best_cand = sorted_by_score[0]
        peak_cand = sorted_by_score[-1]

        # Build Primary Best Window
        best_window = self._build_window_period(
            best_cand,
            duration,
            label="Lowest Forecast Pollution Period",
            activity=activity,
            is_vulnerable=is_vulnerable,
        )

        # Build Peak / Highest Pollution Window
        peak_window = self._build_window_period(
            peak_cand,
            duration,
            label="Higher Pollution Period",
            activity=activity,
            is_vulnerable=is_vulnerable,
        )

        # Identify up to 2 distinct non-overlapping alternative windows
        alt_windows: List[BestAirWindowPeriod] = []
        for cand in sorted_by_score[1:]:
            # Check non-overlap with best_cand (at least 3 hours apart)
            if abs(cand["start_idx"] - best_cand["start_idx"]) >= max(3, duration):
                # Ensure it's not identical to peak
                if cand["start_idx"] != peak_cand["start_idx"]:
                    alt_win = self._build_window_period(
                        cand,
                        duration,
                        label="Comparatively Better Window",
                        activity=activity,
                        is_vulnerable=is_vulnerable,
                    )
                    alt_windows.append(alt_win)
                    if len(alt_windows) >= 2:
                        break

        return AirWindowResponse(
            city=city_meta.name,
            activity=activity,
            duration_hours=duration,
            generated_at=now_dt,
            data_provider="Open-Meteo Atmospheric Chemistry (CAMS & ECMWF)",
            data_provenance_type="atmospheric_model",
            confidence="moderate",
            status="available",
            best_window=best_window,
            peak_pollution_window=peak_window,
            alternative_windows=alt_windows,
            hourly_forecast=hourly_points[:48],
        )

    def _build_window_period(
        self,
        candidate: dict,
        duration: int,
        label: str,
        activity: str,
        is_vulnerable: bool,
    ) -> BestAirWindowPeriod:
        score = candidate["avg_score"]
        act_lower = activity.lower()
        is_cardio = any(k in act_lower for k in ["run", "jog", "cycle", "intense", "workout", "cardio"])

        # Determine strenuous outdoor allowance based on CPCB health thresholds
        if score > 300:  # Very Poor or Severe
            strenuous_allowed = False
            if label == "Higher Pollution Period":
                suitability = (
                    "Peak atmospheric accumulation period. Minimize outdoor exposure and postpone outdoor exertion."
                )
            else:
                suitability = (
                    "Even during this lowest forecast period, atmospheric pollution is projected in the "
                    "Very Poor or Severe band (comparative score > 300). Strenuous outdoor exertion (e.g., running, "
                    "cycling) is NOT recommended; substitute with indoor low-impact movement."
                )
        elif score > 200:  # Poor
            strenuous_allowed = False if (is_vulnerable or is_cardio) else True
            if label == "Higher Pollution Period":
                suitability = (
                    "Elevated pollution accumulation period. Reduce outdoor transit and avoid high-intensity workouts."
                )
            else:
                suitability = (
                    "Comparatively better diurnal dispersion window. Suitable for essential walking or commuting; "
                    "high-intensity outdoor cardio should be moderated or shifted indoors for sensitive groups."
                )
        elif score > 100:  # Moderate
            strenuous_allowed = not is_vulnerable
            if label == "Higher Pollution Period":
                suitability = "Period of higher diurnal concentration. Less optimal for extended outdoor activities."
            else:
                suitability = (
                    "Acceptable diurnal window for outdoor activities; individuals with respiratory sensitivities "
                    "should monitor symptoms."
                )
        else:  # Good or Satisfactory
            strenuous_allowed = True
            suitability = "Favorable atmospheric dispersion window for planned outdoor activities."

        precautionary_notes = [
            "Notice: 'Comparatively better' indicates relative diurnal minimum and does not imply zero particulate exposure.",
            "Verify real-time localized ground station telemetry before commencing long-duration outdoor workouts.",
        ]
        if is_vulnerable:
            precautionary_notes.append(
                "Sensitive individuals (asthma, COPD, children, seniors) should adhere to their management plan."
            )

        return BestAirWindowPeriod(
            start_time=candidate["start_time"],
            end_time=candidate["end_time"],
            start_iso=candidate["start_iso"],
            end_iso=candidate["end_iso"],
            duration_hours=duration,
            average_comparative_score=score,
            score_label=label,
            dominant_pollutant=candidate["dominant_pollutant"],
            strenuous_outdoor_allowed=strenuous_allowed,
            activity_suitability=suitability,
            precautionary_notes=precautionary_notes,
        )

    def _calculate_end_label(self, start_label: str) -> str:
        try:
            parts = start_label.split(":")
            h = (int(parts[0]) + 1) % 24
            return f"{h:02d}:{parts[1]}"
        except Exception:
            return start_label

    def _build_insufficient_response(
        self, city_name: str, activity: str, duration: int, generated_at: datetime
    ) -> AirWindowResponse:
        return AirWindowResponse(
            city=city_name,
            activity=activity,
            duration_hours=duration,
            generated_at=generated_at,
            data_provenance_type="unavailable",
            confidence="unverified",
            status="insufficient_data",
            disclaimer="Insufficient forecast arrays retrieved from atmospheric model. Try again shortly.",
        )


air_window_service = AirWindowService()
