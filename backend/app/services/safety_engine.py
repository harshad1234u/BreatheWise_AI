"""
Deterministic Public-Health Safety Engine.
Operates 100% independently of LLMs.
Based on:
- Central Pollution Control Board (CPCB) NAQI Health Statements (2014)
- Ministry of Health & Family Welfare (MoHFW) NPCCHH Public Health Advisory (2019)
- WHO Global Air Quality Guidelines (2021)
- ICMR & AIIMS Guidelines on Air Pollution Exposure
"""

from typing import List, Optional
from app.schemas.air_quality import NormalizedAirObservation
from app.schemas.plan import HouseholdProfile, SafetyConstraints, StructuredSafetyGuidance


class SafetyEngine:
    """
    Deterministic rules engine converting air quality observations and household
    vulnerability into bounded public-health safety constraints.
    """

    SOURCES: List[str] = [
        "Central Pollution Control Board (CPCB) NAQI Guidelines (2014)",
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
            concerns.append("Fine combustion particles penetrate deep into alveoli and bloodstream.")
        elif "PM10" in dp:
            concerns.append("Coarse particulates irritate upper respiratory airways, eyes, and nasal passages.")
        elif "O3" in dp:
            concerns.append("Photochemical ground-level ozone causes airway inflammation and chest tightness, particularly during sunny afternoons.")
        elif "NO2" in dp:
            concerns.append("Traffic exhaust nitrogen dioxide increases airway hyper-responsiveness.")

        if band in ["Poor", "Very Poor", "Severe"]:
            concerns.append("Elevated ambient pollution increases systemic cardiovascular and respiratory stress during physical exertion.")
        elif band == "Moderate":
            concerns.append("Prolonged strenuous outdoor activity may trigger fatigue or mild coughing in sensitive individuals.")
        else:
            concerns.append("Minimal ambient environmental health burden detected.")
        return concerns

    def evaluate(
        self,
        obs: NormalizedAirObservation,
        profile: Optional[HouseholdProfile] = None
    ) -> StructuredSafetyGuidance:
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
                fallback_indoor_activity="Indoor stretching or yoga",
                source_reference="CPCB NAQI Table 4: Minimal impact"
            )
            general = "Outdoor physical activities, commuting, and sports are encouraged under current conditions."
            children = "Normal outdoor playtime and sports activities are suitable for children."
            seniors = "Normal outdoor walks and routine activities are safe. Monitor general hydration."
            respiratory = "No major restrictions; keep normal prescribed medications available as routine practice."
            commuters_athletes = "Outdoor running, cycling, and active commuting are encouraged."
            indoor_vent = "Open windows for whole-house natural cross-ventilation during pleasant outdoor weather."
            indoor_cooking = "Operate kitchen exhaust fan during frying to maintain fresh indoor baseline."

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
                source_reference="CPCB NAQI Table 4: Breathing discomfort to people with lungs, asthma and heart diseases"
            )
            general = "Outdoor activities are generally acceptable; take periodic rest breaks during prolonged strenuous exertion."
            children = "Children can participate in outdoor activities, but watch for coughing or fatigue during intense games."
            seniors = "Seniors should avoid intense outdoor exertion along busy road corridors with heavy vehicular traffic."
            respiratory = "Individuals with asthma or cardiopulmonary disease should carry their prescribed quick-relief inhaler."
            commuters_athletes = "Athletes should schedule outdoor workouts with adequate hydration; reduce continuous high-intensity sprints."
            indoor_vent = "Window ventilation is acceptable; consider closing windows during peak morning and evening traffic hours."
            indoor_cooking = "Turn on exhaust fan or kitchen chimney before heating oil to exhaust localized cooking aerosols."

        elif band == "Poor":
            constraints = SafetyConstraints(
                calculated_band=band,
                dominant_pollutant=dominant_pollutant,
                outdoor_exertion_level="light_only",
                vulnerable_activity_restriction="indoor_only",
                ventilation_guidance="midday_only",
                respirator_advisory="n95_advised_prolonged",
                indoor_mitigation_required=True,
                fallback_indoor_activity="Indoor low-impact Pilates, core workout, or light treadmill walking",
                source_reference="CPCB NAQI Table 4: Breathing discomfort to most people on prolonged exposure"
            )
            general = "Reduce prolonged high-intensity outdoor workouts. Substitute intense outdoor cardio with indoor exercises."
            children = "Children should avoid prolonged outdoor sports practice; shift physical games indoors where feasible."
            seniors = "Seniors should avoid early morning walks when thermal inversion traps ground-level pollution."
            respiratory = "People with asthma or COPD should limit outdoor exposure and consult physician if wheezing develops."
            commuters_athletes = "For open two-wheeler or auto commutes exceeding 20 minutes, a well-fitted N95/FFP2 respirator is advised."
            indoor_vent = "Ventilate briefly only during middle daylight hours when air disperses; keep windows sealed at dawn and dusk."
            indoor_cooking = "Keep kitchen doors closed while preparing high-heat tadka/frying to prevent smoke migration into living areas."

        elif band in ["Very Poor", "Severe"]:
            constraints = SafetyConstraints(
                calculated_band=band,
                dominant_pollutant=dominant_pollutant,
                outdoor_exertion_level="avoid_all" if band == "Severe" else "avoid_strenuous",
                vulnerable_activity_restriction="strict_shelter" if band == "Severe" else "indoor_only",
                ventilation_guidance="sealed_preferred",
                respirator_advisory="n95_strongly_advised",
                indoor_mitigation_required=True,
                fallback_indoor_activity="Gentle indoor stretching, indoor breathing exercises, or restorative rest",
                source_reference="CPCB NAQI Table 4: Respiratory illness on prolonged exposure / Serious impact on health"
            )
            general = "Avoid non-essential outdoor physical exertion. Limit outdoor time to essential transit."
            children = "Children should remain indoors. Outdoor school sports and playground sessions should be suspended."
            seniors = "Seniors should stay in comfortable indoor spaces and avoid stepping outside into smoggy air."
            respiratory = "High vulnerability alert: vulnerable individuals must keep emergency inhalers ready and avoid all outdoor transit."
            commuters_athletes = "Avoid outdoor running and cycling. N95/FFP2 particulate respirators strongly advised for all outdoor transit; prefer closed Metro."
            indoor_vent = "Keep windows and exterior doors closed to minimize outdoor particle infiltration. Practice damp wet-mopping."
            indoor_cooking = "Run kitchen exhaust fan on high. Avoid burning incense (agarbatti), mosquito coils, or candles indoors."

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
