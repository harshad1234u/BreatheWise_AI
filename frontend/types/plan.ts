import { NormalizedAirObservation } from './air-quality';

export type PersonaType = 'parent' | 'senior' | 'athlete' | 'commuter' | 'general';
export type AgeGroup = 'infant_toddler' | 'child' | 'adult' | 'senior';
export type CommuteMode = 'two_wheeler' | 'open_auto' | 'metro_train' | 'closed_car' | 'walking' | 'none';
export type KitchenVentilation = 'exhaust_fan' | 'chimney' | 'window_only' | 'none';

export interface HouseholdProfile {
  profile_id: string;
  display_name?: string;
  city: string;
  preferred_station_id?: string | null;
  persona: PersonaType;
  age_groups: AgeGroup[];
  has_respiratory_sensitivity: boolean;
  has_cardiovascular_sensitivity: boolean;
  commute_mode?: CommuteMode;
  has_air_purifier: boolean;
  kitchen_ventilation_type: KitchenVentilation;
  activity_preferences?: string[];
}

export interface SafetyConstraints {
  calculated_band: string;
  dominant_pollutant: string;
  outdoor_exertion_level: 'unrestricted' | 'moderate_with_breaks' | 'light_only' | 'avoid_strenuous' | 'avoid_all';
  vulnerable_activity_restriction: 'none' | 'monitor_symptoms' | 'indoor_only' | 'strict_shelter';
  ventilation_guidance: 'unrestricted' | 'close_traffic_peaks' | 'midday_only' | 'sealed_preferred';
  respirator_advisory: 'none' | 'optional_dust_zones' | 'n95_advised_prolonged' | 'n95_strongly_advised';
  indoor_mitigation_required: boolean;
  fallback_indoor_activity: string;
  source_reference: string;
}

export interface StructuredSafetyGuidance {
  band: string;
  dominant_pollutant: string;
  data_confidence: string;
  source_type: string;
  exposure_concerns: string[];
  constraints: SafetyConstraints;
  general_population_guidance: string;
  children_guidance: string;
  senior_guidance: string;
  respiratory_guidance: string;
  commuters_athletes_guidance: string;
  indoor_ventilation_guidance: string;
  indoor_cooking_guidance: string;
  authoritative_sources: string[];
}

export interface PlanRecommendation {
  period: 'morning' | 'afternoon' | 'evening';
  time_window: string;
  activity: string;
  location_type: 'indoor' | 'outdoor' | 'transit';
  intensity: 'none' | 'light' | 'moderate' | 'high';
  explanation: string;
  precautions?: string | null;
  data_context_used: string;
}

export interface DailyPlanResponse {
  plan_id: string;
  generated_at: string;
  ai_provider_used: 'groq' | 'gemini' | 'deterministic_fallback';
  is_fallback: boolean;
  data_provenance: NormalizedAirObservation;
  household_profile: HouseholdProfile;
  safety_guidance: StructuredSafetyGuidance;
  morning: PlanRecommendation[];
  afternoon: PlanRecommendation[];
  evening: PlanRecommendation[];
  indoor_air_suggestions: string[];
  sustainable_alternatives: string[];
  disclaimer: string;
}
