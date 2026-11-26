"""
Deterministic Public-Health Safety Engine.
Operates 100% independently of LLMs.
Authoritative public-health frameworks:
- Central Pollution Control Board (CPCB) NAQI Health Statements (2014) Table 4
- Ministry of Health & Family Welfare (MoHFW) NPCCHH Public Health Advisory on Air Pollution (2019)
- WHO Global Air Quality Guidelines (2021)
- Indian Council of Medical Research (ICMR) Task Force on Environmental Health
"""

from typing import List, Optional
from app.schemas.air_quality import NormalizedAirObservation
from app.schemas.plan import HouseholdProfile, SafetyConstraints, StructuredSafetyGuidance
from app.services.air_quality.freshness import map_us_epa_to_safety_severity


class SafetyEngine:
    """
    Deterministic rules engine converting air quality observations and household
    vulnerability into bounded public-health safety constraints.
    Avoids universal blanket mandates; accounts for indoor cooking, ventilation,
    and transit exposure context.
    """

    SOURCES: List[str] = [
        "Central Pollution Control Board (CPCB) NAQI Guidelines (2014) Table 4",
        "Ministry of Health and Family Welfare (MoHFW) NPCCHH Advisory (2019)",
        "WHO Global Air Quality Guidelines (2021)",
        "Indian Council of Medical Research (ICMR) Environmental Health Guidance"
    ]

    @staticmethod
    def identify_dominant_pollutant(obs: NormalizedAirObservation) -> str:
        """Finds which criteria pollutant has the highest calculated sub-index."""
        pollutant_sub_indices = {
            "PM2.5": obs.pm25.sub_index if obs.pm25 else None,
            "PM10": obs.pm10.sub_index if obs.pm10 else None,
            "NO2": obs.no2.sub_index if obs.no2 else None,
            "SO2": obs.so2.sub_index if obs.so2 else None,
            "CO": obs.co.sub_index if obs.co else None,
            "O3": obs.o3.sub_index if obs.o3 else None,
            "NH3": obs.nh3.sub_index if obs.nh3 else None,
            "Pb": obs.pb.sub_index if obs.pb else None,
        }
        valid = {k: v for k, v in pollutant_sub_indices.items() if v is not None}
        if not valid:
            return "PM2.5 (Default)"
        return max(valid.items(), key=lambda x: x[1])[0]

    @staticmethod
    def get_exposure_concerns(dominant_pollutant: str, band: str) -> List[str]:
        concerns = []
        dp = dominant_pollutant.upper()
        if "PM2.5" in dp:
            concerns.append("Fine combustion particles penetrate deep into alveoli and cardiovascular pathways.")
        elif "PM10" in dp:
            concerns.append("Coarse particulates irritate upper respiratory airways, eyes, and nasal passages.")
        elif "O3" in dp:
            concerns.append("Ground-level ozone triggers airway inflammation, particularly during warm, sunlit midday hours.")
        elif "NO2" in dp:
            concerns.append("Traffic exhaust nitrogen dioxide increases airway reactivity and mucosal irritation.")

        if band in ["Poor", "Very Poor", "Severe"]:
            concerns.append("Elevated ambient pollution increases systemic cardiovascular and respiratory strain during prolonged exertion.")
        elif band == "Moderate":
            concerns.append("Prolonged strenuous outdoor activity may cause mild discomfort or coughing in sensitive groups.")
        else:
            concerns.append("Minimal ambient environmental health burden detected.")
        return concerns

    def evaluate(
        self,
        obs: NormalizedAirObservation,
        profile: Optional[HouseholdProfile] = None
    ) -> StructuredSafetyGuidance:
        # Scale-aware severity interpretation: never apply CPCB index bands literally to US-EPA AQI values
        if obs.index_type == "provider_index" and obs.index_value is not None:
            band = map_us_epa_to_safety_severity(obs.index_value)
        else:
            band = obs.index_category
        dominant_pollutant = self.identify_dominant_pollutant(obs)
        concerns = self.get_exposure_concerns(dominant_pollutant, band)

        # Base deterministic constraints per CPCB Category
        if band in ["Good", "Satisfactory"]:
            constraints = SafetyConstraints(
                calculated_band=band,
                dominant_pollutant=dominant_pollutant,
                outdoor_exertion_level="unrestricted",
                vulnerable_activity_restriction="none",
                ventilation_guidance="unrestricted",
                respirator_advisory="none",
                indoor_mitigation_required=False,
                fallback_indoor_activity="Indoor stretching or mobility drills",
                source_reference="CPCB NAQI Table 4: Minimal impact"
            )
            general = "Ambient air quality is acceptable. Outdoor physical activities, commuting, and sports are encouraged under current conditions."
            children = "Children can participate in standard outdoor play and school sports."
            seniors = "Routine outdoor walks and daily activities are supported. Maintain standard hydration."
            respiratory = "Individuals with asthma or cardiopulmonary disease may maintain routine access to physician-prescribed management."
            commuters_athletes = "Outdoor running, cycling, and active commuting are supported."
            indoor_vent = "Natural cross-ventilation and open windows are suitable during clear ambient weather."
            indoor_cooking = "Operate kitchen exhaust fan during frying or high-heat cooking to maintain clean indoor air."

        elif band == "Moderate":
            constraints = SafetyConstraints(
                calculated_band=band,
                dominant_pollutant=dominant_pollutant,
                outdoor_exertion_level="moderate_with_breaks",
                vulnerable_activity_restriction="monitor_symptoms",
                ventilation_guidance="close_traffic_peaks",
                respirator_advisory="optional_dust_zones",
                indoor_mitigation_required=False,
                fallback_indoor_activity="Indoor bodyweight circuit or mobility drills",
                source_reference="CPCB NAQI Table 4: Discomfort to people with lungs, asthma and heart diseases"
            )
            general = "Outdoor activities are generally acceptable; take periodic rest breaks during prolonged strenuous exertion."
            children = "Children can participate in outdoor recreation; monitor sensitive children for unusual coughing or breathlessness."
            seniors = "Older adults, especially those with cardiopulmonary conditions, may consider reducing intense outdoor exertion along heavy traffic corridors."
            respiratory = "Individuals with diagnosed respiratory sensitivities should keep their physician-prescribed rescue inhalers accessible."
            commuters_athletes = "Athletes should schedule outdoor workouts with adequate hydration; reduce continuous high-intensity sprints near busy roads."
            indoor_vent = "Window ventilation is acceptable; consider closing windows facing heavy traffic during morning and evening rush hours."
            indoor_cooking = "Turn on exhaust fan or chimney before heating oil to exhaust localized cooking aerosols."

        elif band == "Poor":
            constraints = SafetyConstraints(
                calculated_band=band,
                dominant_pollutant=dominant_pollutant,
                outdoor_exertion_level="light_only",
                vulnerable_activity_restriction="indoor_only",
                ventilation_guidance="managed_ventilation",
                respirator_advisory="n95_advised_prolonged",
                indoor_mitigation_required=True,
                fallback_indoor_activity="Indoor low-impact Pilates, core workout, or light treadmill walking",
                source_reference="CPCB NAQI Table 4: Breathing discomfort to most people on prolonged exposure"
            )
            general = "Consider reducing prolonged high-intensity outdoor workouts. Substitute intense outdoor cardio with indoor physical activities."
            children = "Children, especially those with reactive airways, are advised to limit prolonged outdoor strenuous play."
            seniors = "Older adults are advised to avoid prolonged strenuous exertion near busy traffic corridors."
            respiratory = "People with chronic respiratory conditions should minimize strenuous outdoor exertion and consult their healthcare provider if wheezing develops."
            commuters_athletes = "For open transit (e.g. two-wheelers, auto-rickshaws) exceeding 20-30 minutes along heavy traffic corridors, a certified particulate respirator (N95/FFP2) is recommended to reduce particulate inhalation. In enclosed transport, respirators are optional."
            indoor_vent = "Keep windows closed against ambient smog when outdoor pollution is elevated, but ensure mechanical exhaust (chimney or kitchen fan) is active when cooking or using gas stoves to prevent trapping harmful indoor combustion gases."
            indoor_cooking = "Run kitchen exhaust fan on high. Keep interior kitchen doors closed during high-heat frying or tadka to prevent smoke migration into living spaces."

        elif band in ["Very Poor", "Severe"]:
            constraints = SafetyConstraints(
                calculated_band=band,
                dominant_pollutant=dominant_pollutant,
                outdoor_exertion_level="avoid_all" if band == "Severe" else "avoid_strenuous",
                vulnerable_activity_restriction="strict_shelter" if band == "Severe" else "indoor_preferred",
                ventilation_guidance="managed_ventilation",
                respirator_advisory="n95_strongly_advised",
                indoor_mitigation_required=True,
                fallback_indoor_activity="Gentle indoor stretching, indoor breathing exercises, or restorative rest",
                source_reference="CPCB NAQI Table 4: Respiratory illness on prolonged exposure / Severe impact"
            )
            general = "Avoid non-essential strenuous outdoor physical exertion. Limit outdoor exposure to necessary transit."
            children = "Children and school cohorts should prioritize indoor play and study; avoid strenuous outdoor sports competitions during severe air episodes."
            seniors = "Older adults should stay in cleaner indoor environments and avoid outdoor physical exertion during heavy smog."
            respiratory = "Individuals with asthma, COPD, or cardiovascular disease should avoid outdoor exertion, keep physician-prescribed rescue inhalers accessible, and consult their healthcare provider if symptoms increase."
            commuters_athletes = "Avoid continuous outdoor running or cycling. When traveling in open transit modes (two-wheelers, open auto) in heavy smog, wearing a well-fitted particulate respirator (N95 or FFP2) can meaningfully reduce particle inhalation. When using enclosed Metro or AC cabs, respirators are optional."
            indoor_vent = "Keep exterior windows closed to mitigate outdoor particulate infiltration. However, if indoor combustion (cooking, gas burners) occurs, active kitchen mechanical exhaust is essential to prevent indoor pollutant trapping. Damp wet-mopping helps settle indoor dust without resuspending coarse particles."
            indoor_cooking = "Operate kitchen exhaust fan on high during cooking. Avoid burning incense sticks (agarbatti), dhoop, mosquito coils, or candles indoors, as these release significant fine particulate matter into sealed rooms."

        else:
            # Fallback for Unavailable
            constraints = SafetyConstraints(
                calculated_band="Unavailable",
                dominant_pollutant=dominant_pollutant,
                outdoor_exertion_level="unrestricted",
                vulnerable_activity_restriction="none",
                ventilation_guidance="unrestricted",
                respirator_advisory="none",
                indoor_mitigation_required=False,
                fallback_indoor_activity="Standard indoor exercises",
                source_reference="CPCB NAQI Guidelines (Data Unavailable)"
            )
            general = "Environmental telemetry is currently unavailable. Follow general seasonal precautions."
            children = "Follow standard school and daily routines."
            seniors = "Follow standard health routines."
            respiratory = "Maintain standard access to prescribed medications."
            commuters_athletes = "Proceed with normal travel, monitoring local conditions."
            indoor_vent = "Ventilate indoor spaces as needed based on local weather."
            indoor_cooking = "Maintain routine kitchen exhaust ventilation."

        # Adapt for specific household profile sensitivities if provided
        if profile and (profile.has_respiratory_sensitivity or profile.has_cardiovascular_sensitivity):
            if band in ["Moderate", "Poor"]:
                constraints.vulnerable_activity_restriction = "indoor_only"
                constraints.respirator_advisory = "n95_advised_prolonged"

        return StructuredSafetyGuidance(
            band=band,
            dominant_pollutant=dominant_pollutant,
            data_confidence=obs.confidence_score,
            source_type=obs.source_type,
            exposure_concerns=concerns,
            constraints=constraints,
            general_population_guidance=general,
            children_guidance=children,
            senior_guidance=seniors,
            respiratory_guidance=respiratory,
            commuters_athletes_guidance=commuters_athletes,
            indoor_ventilation_guidance=indoor_vent,
            indoor_cooking_guidance=indoor_cooking,
            authoritative_sources=self.SOURCES,
        )


safety_engine = SafetyEngine()
