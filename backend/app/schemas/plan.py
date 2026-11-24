from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from app.schemas.air_quality import NormalizedAirObservation


class HouseholdProfile(BaseModel):
    profile_id: str = Field(default="guest_default")
    display_name: Optional[str] = "My Household"
    city: str
    preferred_station_id: Optional[str] = None
    persona: Literal["parent", "senior", "athlete", "commuter", "general"] = "general"
    age_groups: List[Literal["infant_toddler", "child", "adult", "senior"]] = ["adult"]
    has_respiratory_sensitivity: bool = False
    has_cardiovascular_sensitivity: bool = False
    commute_mode: Optional[Literal["two_wheeler", "open_auto", "metro_train", "closed_car", "walking", "none"]] = "metro_train"
    has_air_purifier: bool = False
    kitchen_ventilation_type: Literal["exhaust_fan", "chimney", "window_only", "none"] = "exhaust_fan"
    activity_preferences: Optional[List[str]] = None


class SafetyConstraints(BaseModel):
    calculated_band: str
    dominant_pollutant: str
    outdoor_exertion_level: Literal["unrestricted", "moderate_with_breaks", "light_only", "avoid_strenuous", "avoid_all"]
    vulnerable_activity_restriction: Literal[
        "none", "monitor_symptoms", "indoor_only", "strict_shelter", "indoor_preferred", "minimize_strenuous_outdoor"
    ]
    ventilation_guidance: Literal[
        "unrestricted", "close_traffic_peaks", "midday_only", "sealed_preferred", "managed_ventilation"
    ]
    respirator_advisory: Literal[
        "none", "optional_dust_zones", "n95_advised_prolonged", "n95_strongly_advised", "n95_situational_prolonged"
    ]
    indoor_mitigation_required: bool
    fallback_indoor_activity: str
    source_reference: str = "CPCB National Air Quality Index (2014) & MoHFW NPCCHH (2019)"


class StructuredSafetyGuidance(BaseModel):
    band: str
    dominant_pollutant: str
    data_confidence: str
    source_type: str
    exposure_concerns: List[str]
    constraints: SafetyConstraints
    general_population_guidance: str
    children_guidance: str
    senior_guidance: str
    respiratory_guidance: str
    commuters_athletes_guidance: str
    indoor_ventilation_guidance: str
    indoor_cooking_guidance: str
    authoritative_sources: List[str]


class PlanRecommendation(BaseModel):
    period: Literal["morning", "afternoon", "evening"]
    time_window: str
    activity: str
    location_type: Literal["indoor", "outdoor", "transit"]
    intensity: Literal["none", "light", "moderate", "high"] = "none"
    explanation: str
    precautions: Optional[str] = None
    data_context_used: str


class DailyPlanResponse(BaseModel):
    plan_id: str
    generated_at: datetime
    ai_provider_used: Literal["groq", "gemini", "deterministic_fallback"]
    is_fallback: bool
    data_provenance: NormalizedAirObservation
    household_profile: HouseholdProfile
    safety_guidance: StructuredSafetyGuidance
    
    # 3-Period Structured Recommendations
    morning: List[PlanRecommendation]
    afternoon: List[PlanRecommendation]
    evening: List[PlanRecommendation]
    
    # Pillar Guidance
    indoor_air_suggestions: List[str]
    sustainable_alternatives: List[str]
    
    disclaimer: str
