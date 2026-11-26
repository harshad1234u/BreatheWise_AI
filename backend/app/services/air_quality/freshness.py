from datetime import datetime, timezone
from typing import Literal, Optional, Tuple
from app.core.config import settings

FreshnessStatus = Literal["live", "stale", "expired", "unavailable"]


def evaluate_observation_freshness(
    time_iso: Optional[str],
    now_utc: Optional[datetime] = None,
    stale_after_hours: Optional[float] = None,
    expire_after_hours: float = 24.0,
) -> Tuple[Optional[datetime], FreshnessStatus, Optional[str]]:
    """
    Parses a provider observation timestamp into timezone-aware UTC and classifies freshness:
    - <= stale_after_hours (default 3h): 'live'
    - > stale_after_hours and <= expire_after_hours (24h): 'stale'
    - > expire_after_hours (24h): 'expired'
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
        # Assume UTC if offset was omitted rather than guessing local host timezone
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)

    ref_now = (now_utc or datetime.now(timezone.utc)).astimezone(timezone.utc)
    threshold = stale_after_hours if stale_after_hours is not None else float(settings.GROUND_DATA_FRESHNESS_HOURS)
    age_hours = (ref_now - parsed).total_seconds() / 3600.0

    # Slight clock-skew tolerance (-0.25h) treated as live; large future timestamps flagged unavailable
    if age_hours < -0.5:
        return parsed, "unavailable", "Observation timestamp is abnormally far in the future"
    if age_hours <= threshold:
        return parsed, "live", None
    if age_hours <= expire_after_hours:
        return parsed, "stale", f"Observation is {age_hours:.1f}h old (older than {int(threshold)}h freshness threshold)"
    return parsed, "expired", f"Observation is {age_hours:.1f}h old (expired > {int(expire_after_hours)}h)"


def map_us_epa_aqi_to_display_category(aqi_val: Optional[float]) -> str:
    """
    Maps a US-EPA AQI value (0-500+) to standard display category names compatible with
    the application palette without claiming it is a CPCB concentration sub-index.
    """
    if aqi_val is None or aqi_val < 0:
        return "Unavailable"
    if aqi_val <= 50:
        return "Good"
    if aqi_val <= 100:
        return "Moderate"
    if aqi_val <= 150:
        return "Moderate (Sensitive)"
    if aqi_val <= 200:
        return "Poor"
    if aqi_val <= 300:
        return "Very Poor"
    return "Severe"
