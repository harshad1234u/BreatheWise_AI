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
    3. Provides contextual, non-mandatory respirator advice tailored to commute mode and exposure duration.
    4. Ensures no medical diagnoses or prescriptions are passed through.
    5. Balances indoor cooking emissions with outdoor pollution infiltration.
    """
    if not isinstance(raw_json, dict):
        return None

    periods = ["morning", "afternoon", "evening"]
    validated_plan: Dict[str, Any] = {}
    constraints = safety.constraints
    commute_mode = getattr(profile, "commute_mode", "metro_train") or "metro_train"

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

            # Guardrail 1: Enforce outdoor exertion restrictions (CPCB Table 4)
            if constraints.outdoor_exertion_level in ["avoid_strenuous", "avoid_all"]:
                if loc == "outdoor" and intensity in ["moderate", "high"]:
                    act = f"{constraints.fallback_indoor_activity} (Substituted)"
                    loc = "indoor"
                    intensity = "light"
                    expl += " Shifted to indoor low-intensity exertion to mitigate deep particulate inhalation under elevated ambient pollution."
                    prec_str = (
                        (prec_str + " | " if prec_str else "") +
                        "Safety Engine Guardrail: Outdoor high exertion shifted indoors to protect respiratory health (CPCB Guidelines)."
                    )

            # Guardrail 2: Contextual, non-blanket transit guidance
            # Respirators are recommended for open road travel, NOT mandated for every closed space
            if constraints.respirator_advisory in ["n95_advised_prolonged", "n95_strongly_advised"]:
                if loc == "transit":
                    is_open_commute = commute_mode in ["two_wheeler", "open_auto", "walking"]
                    if is_open_commute and "respirator" not in (prec_str or "").lower() and "n95" not in (prec_str or "").lower():
                        prec_str = (
                            (prec_str + " | " if prec_str else "") +
                            "Certified N95/FFP2 particulate respirator recommended during open-air transit in heavy traffic."
                        )
                    elif not is_open_commute and "respirator" not in (prec_str or "").lower():
                        prec_str = (
                            (prec_str + " | " if prec_str else "") +
                            "Enclosed transit: keep vehicle windows closed; respirators optional inside filtered vehicles/Metro."
                        )

            # Guardrail 3: Remove universal "safe time" claims
            for unsafe_claim in ["completely safe", "safe period", "safe hour", "zero pollution"]:
                if unsafe_claim in expl.lower():
                    expl = expl.replace(unsafe_claim, "comparatively lower exposure period")

            # Guardrail 4: Strip any unauthorized medication prescriptions
            for med_term in ["take steroid", "take antibiotic", "dosage", "prescribe"]:
                if med_term in expl.lower() or (prec_str and med_term in prec_str.lower()):
                    expl = "Consult your physician for personalized medical advice regarding existing conditions."
                    prec_str = "Keep physician-prescribed medications accessible."

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

    # Validate indoor suggestions (must balance cooking exhaust with ambient infiltration)
    indoor_suggs = raw_json.get("indoor_air_suggestions")
    if not isinstance(indoor_suggs, list) or len(indoor_suggs) == 0:
        indoor_suggs = [safety.indoor_ventilation_guidance, safety.indoor_cooking_guidance]
    else:
        # Sanitize any blanket statements that say "never open windows under any circumstances"
        clean_suggs = []
        for s in indoor_suggs:
            st = str(s)
            if "never open" in st.lower() and "cooking" not in st.lower():
                st += " (Note: Always operate kitchen exhaust/chimney during cooking to avoid trapping indoor emissions)."
            clean_suggs.append(st)
        indoor_suggs = clean_suggs
    validated_plan["indoor_air_suggestions"] = [str(s) for s in indoor_suggs]

    sust_alts = raw_json.get("sustainable_alternatives")
    if not isinstance(sust_alts, list) or len(sust_alts) == 0:
        sust_alts = [
            "Opt for closed mass transit (Metro / electric bus) over open two-wheelers during heavy pollution episodes to reduce personal inhalation while lowering road emissions.",
            "Consolidate daily market and commercial errands into a single trip during off-peak traffic hours."
        ]
    validated_plan["sustainable_alternatives"] = [str(a) for a in sust_alts]

    return validated_plan


def generate_deterministic_fallback_plan(
    observation: NormalizedAirObservation,
    profile: HouseholdProfile,
    safety: StructuredSafetyGuidance,
    air_window_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Pure Python deterministic daily plan generator.
    Triggered when both Groq and Gemini fail, rate limit, or time out.
    Guarantees 100% application resilience with source-backed CPCB advice.
    """
    constraints = safety.constraints
    band = observation.index_category
    commute_mode = getattr(profile, "commute_mode", "metro_train") or "metro_train"
    is_open_commute = commute_mode in ["two_wheeler", "open_auto", "walking"]

    forecast_note = ""
    if air_window_context and "start_time" in air_window_context:
        w_start = air_window_context.get("start_time")
        w_end = air_window_context.get("end_time")
        forecast_note = f" (Atmospheric CAMS forecast indicates comparatively lower exposure window around {w_start} - {w_end})."

    # Morning
    if constraints.outdoor_exertion_level in ["avoid_strenuous", "avoid_all"]:
        morning_act = constraints.fallback_indoor_activity
        morning_loc = "indoor"
        morning_intensity = "light"
        morning_expl = f"Surface inversion often traps morning particulate matter ({observation.index_category}). Strenuous outdoor exercise shifted indoors."
        morning_prec = "Keep exterior windows closed during early morning hours; ensure indoor exercise is done in well-filtered or dust-settled space."
    else:
        morning_act = "Outdoor morning walk or active commute"
        morning_loc = "outdoor"
        morning_intensity = "moderate"
        morning_expl = f"Air quality is in the {band} range; suitable for morning physical activity."
        morning_prec = "Stay hydrated and avoid heavy vehicular transit corridors."

    # Afternoon
    afternoon_act = "Midday work & domestic tasks"
    afternoon_loc = "indoor"
    afternoon_intensity = "light"
    if constraints.ventilation_guidance in ["unrestricted", "close_traffic_peaks", "midday_only"]:
        afternoon_expl = f"Midday solar heating aids vertical atmospheric mixing. Brief cross-ventilation can be considered if outdoor air is relatively clearer than indoor air.{forecast_note}"
        afternoon_prec = "Close exterior windows prior to evening rush hour traffic buildup."
    else:
        afternoon_expl = f"Ambient pollution remains elevated ({band}). Keep exterior windows closed, but operate kitchen mechanical exhaust during cooking."
        afternoon_prec = "Run indoor air filtration if available; maintain kitchen exhaust during cooking."

    # Evening
    evening_act = f"Evening return commute via {commute_mode.replace('_', ' ').title()}"
    evening_loc = "transit"
    evening_intensity = "light"
    evening_expl = "Evening rush hour traffic combined with cooling boundary layers increases roadside particulate concentrations."
    if constraints.respirator_advisory in ["n95_advised_prolonged", "n95_strongly_advised"]:
        if is_open_commute:
            evening_prec = "A certified N95/FFP2 particulate respirator is recommended during open two-wheeler or walking commutes in heavy traffic."
        else:
            evening_prec = "Keep vehicle windows closed and set AC to recirculation mode during congested traffic."
    else:
        evening_prec = "Prefer closed transit routes where feasible to reduce personal traffic exhaust exposure."

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
                "data_context_used": f"Midday conditions ({band})",
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
            "Practice damp wet-mopping (pocha) rather than dry broom sweeping (jharoo) to prevent coarse PM10 dust resuspension.",
            "Operate kitchen exhaust fan or chimney on high during cooking; keep kitchen doors closed to prevent tadka aerosols from spreading to living areas.",
            safety.indoor_ventilation_guidance,
        ],
        "sustainable_alternatives": [
            "Choose electric mass-transit (e.g. Metro) over open two-wheelers during heavy pollution to lower personal particulate inhalation while cutting vehicle emissions.",
            "Consolidate daily market and commercial errands into off-peak hours to reduce cumulative traffic exposure.",
        ]
    }
