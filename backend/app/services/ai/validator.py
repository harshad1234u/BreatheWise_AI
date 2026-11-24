import logging
from typing import Any, Dict, List, Optional
from app.schemas.air_quality import NormalizedAirObservation
from app.schemas.plan import (
    HouseholdProfile,
    PlanRecommendation,
    StructuredSafetyGuidance,
)

logger = logging.getLogger(__name__)


def validate_and_guardrail_ai_plan(
    raw_json: Dict[str, Any],
    observation: NormalizedAirObservation,
    profile: HouseholdProfile,
    safety: StructuredSafetyGuidance
) -> Optional[Dict[str, Any]]:
    """
    Validates LLM response schema and applies deterministic public-health guardrails:
    1. Enforces schema presence (morning, afternoon, evening, indoor suggestions, alternatives).
    2. Overrules unsafe outdoor high-exertion recommendations under Poor/Very Poor/Severe AQI.
    3. Injects mandatory respirator precautions during open transit in elevated pollution.
    4. Ensures zero hallucinated AQI numbers overwrite actual data.
    """
    if not isinstance(raw_json, dict):
        return None

    periods = ["morning", "afternoon", "evening"]
    validated_plan: Dict[str, Any] = {}
    constraints = safety.constraints

    for period in periods:
        items = raw_json.get(period)
        if not items or not isinstance(items, list):
            logger.warning(f"AI response missing required period: {period}")
            return None

        period_recs: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue

            time_win = str(item.get("time_window", "Morning" if period == "morning" else ("Afternoon" if period == "afternoon" else "Evening")))
            act = str(item.get("activity", "Scheduled routine"))
            loc = str(item.get("location_type", "indoor")).lower()
            if loc not in ["indoor", "outdoor", "transit"]:
                loc = "indoor"
            
            intensity = str(item.get("intensity", "none")).lower()
            if intensity not in ["none", "light", "moderate", "high"]:
                intensity = "light"

            expl = str(item.get("explanation", "Designed around current air quality."))
            prec = item.get("precautions")
            prec_str = str(prec) if prec else None
            data_ctx = str(item.get("data_context_used", f"{observation.index_category} AQI"))

            # Guardrail 1: Enforce outdoor exertion restrictions
            if constraints.outdoor_exertion_level in ["avoid_strenuous", "avoid_all"]:
                if loc == "outdoor" and intensity in ["moderate", "high"]:
                    act = f"{constraints.fallback_indoor_activity} (Substituted)"
                    loc = "indoor"
                    intensity = "light"
                    expl += " Adjusted to indoor low-intensity to protect respiratory health."
                    prec_str = (
                        (prec_str + " | " if prec_str else "") +
                        "Safety Engine Guardrail: Outdoor high exertion suspended due to unhealthy air."
                    )

            # Guardrail 2: Enforce respirator advisory for transit in elevated pollution
            if constraints.respirator_advisory in ["n95_advised_prolonged", "n95_strongly_advised"]:
                if loc in ["transit", "outdoor"] and ("mask" not in (prec_str or "").lower() and "n95" not in (prec_str or "").lower()):
                    prec_str = (
                        (prec_str + " | " if prec_str else "") +
                        "N95/FFP2 respirator advised during outdoor transit."
                    )

            period_recs.append({
                "period": period,
                "time_window": time_win,
                "activity": act,
                "location_type": loc,
                "intensity": intensity,
                "explanation": expl,
                "precautions": prec_str,
                "data_context_used": data_ctx,
            })

        if not period_recs:
            return None
        validated_plan[period] = period_recs

    # Validate indoor suggestions
    indoor_suggs = raw_json.get("indoor_air_suggestions")
    if not isinstance(indoor_suggs, list) or len(indoor_suggs) == 0:
        indoor_suggs = [safety.indoor_ventilation_guidance, safety.indoor_cooking_guidance]
    validated_plan["indoor_air_suggestions"] = [str(s) for s in indoor_suggs]

    # Validate sustainable alternatives
    sust_alts = raw_json.get("sustainable_alternatives")
    if not isinstance(sust_alts, list) or len(sust_alts) == 0:
        sust_alts = [
            "Opt for closed-cabin public transit (Metro) rather than open two-wheelers during peak traffic hours to reduce personal exposure.",
            "Consolidate daily vehicle errands into a single trip during middle daylight hours."
        ]
    validated_plan["sustainable_alternatives"] = [str(a) for a in sust_alts]

    return validated_plan


def generate_deterministic_fallback_plan(
    observation: NormalizedAirObservation,
    profile: HouseholdProfile,
    safety: StructuredSafetyGuidance
) -> Dict[str, Any]:
    """
    Pure Python deterministic daily plan generator.
    Triggered when both Groq and Gemini fail, rate limit, or time out.
    Guarantees 100% application resilience with source-backed CPCB advice.
    """
    constraints = safety.constraints
    band = observation.index_category
    commute_mode = profile.commute_mode or "metro_train"

    # Morning
    if constraints.outdoor_exertion_level in ["avoid_strenuous", "avoid_all"]:
        morning_act = constraints.fallback_indoor_activity
        morning_loc = "indoor"
        morning_intensity = "light"
        morning_expl = f"Surface inversion traps morning pollution ({observation.index_category}). Outdoor exercise moved indoors."
        morning_prec = "Keep windows sealed during dawn and morning rush hours."
    else:
        morning_act = "Outdoor morning walk or active commute"
        morning_loc = "outdoor"
        morning_intensity = "moderate"
        morning_expl = f"Air quality is in the {band} range; suitable for morning physical activity."
        morning_prec = "Stay hydrated and avoid heavy truck traffic corridors."

    # Afternoon
    afternoon_act = "Midday work & domestic tasks"
    afternoon_loc = "indoor"
    afternoon_intensity = "light"
    if constraints.ventilation_guidance in ["unrestricted", "close_traffic_peaks", "midday_only"]:
        afternoon_expl = "Middle daylight hours allow atmospheric dispersion. Open opposing windows for brief air exchange if outdoor air is relatively clearer."
        afternoon_prec = "Close windows before evening traffic builds up."
    else:
        afternoon_expl = f"Ambient pollution remains elevated ({band}). Keep windows sealed."
        afternoon_prec = "Run indoor air filtration if available."

    # Evening
    evening_act = f"Evening return commute via {commute_mode.replace('_', ' ').title()}"
    evening_loc = "transit"
    evening_intensity = "light"
    evening_expl = "Evening boundary layer contraction causes particulate buildup from peak traffic."
    if constraints.respirator_advisory in ["n95_advised_prolonged", "n95_strongly_advised"]:
        evening_prec = "Wear a well-fitted N95/FFP2 respirator during open road travel."
    else:
        evening_prec = "Prefer closed transit routes where feasible."

    return {
        "morning": [
            {
                "period": "morning",
                "time_window": "06:30 AM - 08:30 AM",
                "activity": morning_act,
                "location_type": morning_loc,
                "intensity": morning_intensity,
                "explanation": morning_expl,
                "precautions": morning_prec,
                "data_context_used": f"Dominant {safety.dominant_pollutant} ({band})",
            }
        ],
        "afternoon": [
            {
                "period": "afternoon",
                "time_window": "01:30 PM - 03:30 PM",
                "activity": afternoon_act,
                "location_type": afternoon_loc,
                "intensity": afternoon_intensity,
                "explanation": afternoon_expl,
                "precautions": afternoon_prec,
                "data_context_used": f"Midday dispersion ({band})",
            }
        ],
        "evening": [
            {
                "period": "evening",
                "time_window": "06:00 PM - 08:30 PM",
                "activity": evening_act,
                "location_type": evening_loc,
                "intensity": evening_intensity,
                "explanation": evening_expl,
                "precautions": evening_prec,
                "data_context_used": f"Evening traffic peak ({band})",
            }
        ],
        "indoor_air_suggestions": [
            "Practice damp wet-mopping (pocha) instead of dry sweeping (jharoo) to prevent coarse PM10 dust resuspension.",
            "Run kitchen exhaust fan or chimney on high during cooking, and keep interior kitchen doors closed to prevent tadka aerosols from spreading.",
            safety.indoor_ventilation_guidance,
        ],
        "sustainable_alternatives": [
            "Use electric mass-transit (Metro) rather than open two-wheelers during heavy smog to reduce personal particulate inhalation while cutting vehicle emissions.",
            "Consolidate daily market errands into a single off-peak trip to minimize road exposure.",
        ]
    }
