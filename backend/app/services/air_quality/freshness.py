from datetime import datetime, timezone
from typing import Literal, Optional, Tuple
from app.core.config import settings

FreshnessStatus = Literal["live", "stale", "expired", "unavailable"]


def evaluate_observation_freshness(
    time_iso: Optional[str],
    now_utc: Optional[datetime] = None,
    stale_after_hours: Optional[float] = None,
    expire_after_hours: float = 12.0,
) -> Tuple[Optional[datetime], FreshnessStatus, Optional[str]]:
    """
    Reconciles observation freshness strictly with PRD v1.2 Section 5.2:
    - <= 3.0 hours (stale_after_hours): 'live'
    - > 3.0 hours and <= 12.0 hours (expire_after_hours): 'stale'
    - > 12.0 hours: 'expired' (ineligible as current ground telemetry; triggers Tier 2 model fallback)
    - Missing or malformed timestamp: (None, 'unavailable', reason) — NEVER stamps current time as 'live'.
    """
    if not time_iso or not isinstance(time_iso, str) or not time_iso.strip():
        return None, "unavailable", "Observation timestamp missing from provider feed"

    cleaned = time_iso.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError:
        return None, "unavailable", f"Malformed observation timestamp: '{time_iso}'"

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)

    ref_now = (now_utc or datetime.now(timezone.utc)).astimezone(timezone.utc)
    threshold = stale_after_hours if stale_after_hours is not None else float(settings.GROUND_DATA_FRESHNESS_HOURS)
    age_hours = (ref_now - parsed).total_seconds() / 3600.0

    if age_hours < -0.5:
        return parsed, "unavailable", "Observation timestamp is abnormally far in the future"
    if age_hours <= threshold:
        return parsed, "live", None
    if age_hours <= expire_after_hours:
        return parsed, "stale", f"Observation is {age_hours:.1f}h old (between {int(threshold)}h and {int(expire_after_hours)}h)"
    return parsed, "expired", f"Observation is {age_hours:.1f}h old (exceeds {int(expire_after_hours)}h current-telemetry limit)"


def map_us_epa_aqi_to_display_category(aqi_val: Optional[float]) -> str:
    """
    Maps a WAQI US-EPA AQI value (0-500+) strictly using official US-EPA AQI category labels,
    never applying CPCB category thresholds or CPCB labels to US-EPA indices.
    """
    if aqi_val is None or aqi_val < 0:
        return "Unavailable"
    if aqi_val <= 50:
        return "Good"
    if aqi_val <= 100:
        return "Moderate"
    if aqi_val <= 150:
        return "Unhealthy for Sensitive Groups"
    if aqi_val <= 200:
        return "Unhealthy"
    if aqi_val <= 300:
        return "Very Unhealthy"
    return "Hazardous"
