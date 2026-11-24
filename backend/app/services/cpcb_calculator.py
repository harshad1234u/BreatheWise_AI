"""
Central Pollution Control Board (CPCB) National Air Quality Index (NAQI) Engine.
Reference: CPCB (2014) National Air Quality Index Report, Ministry of Environment, Forest & Climate Change.
"""

from typing import Dict, List, Optional, Tuple
from app.schemas.air_quality import PollutantConcentration

# Breakpoints: (B_low, B_high, I_low, I_high)
BREAKPOINTS: Dict[str, List[Tuple[float, float, int, int]]] = {
    "pm25": [
        (0.0, 30.0, 0, 50),
        (31.0, 60.0, 51, 100),
        (61.0, 90.0, 101, 200),
        (91.0, 120.0, 201, 300),
        (121.0, 250.0, 301, 400),
        (250.0, 500.0, 401, 500),
    ],
    "pm10": [
        (0.0, 50.0, 0, 50),
        (51.0, 100.0, 51, 100),
        (101.0, 250.0, 101, 200),
        (251.0, 350.0, 201, 300),
        (351.0, 430.0, 301, 400),
        (430.0, 600.0, 401, 500),
    ],
    "no2": [
        (0.0, 40.0, 0, 50),
        (41.0, 80.0, 51, 100),
        (81.0, 180.0, 101, 200),
        (181.0, 280.0, 201, 300),
        (281.0, 400.0, 301, 400),
        (400.0, 800.0, 401, 500),
    ],
    "so2": [
        (0.0, 40.0, 0, 50),
        (41.0, 80.0, 51, 100),
        (81.0, 380.0, 101, 200),
        (381.0, 800.0, 201, 300),
        (801.0, 1600.0, 301, 400),
        (1600.0, 2400.0, 401, 500),
    ],
    "co": [
        (0.0, 1.0, 0, 50),
        (1.1, 2.0, 51, 100),
        (2.1, 10.0, 101, 200),
        (10.1, 17.0, 201, 300),
        (17.1, 34.0, 301, 400),
        (34.0, 50.0, 401, 500),
    ],
    "o3": [
        (0.0, 50.0, 0, 50),
        (51.0, 100.0, 51, 100),
        (101.0, 168.0, 101, 200),
        (169.0, 208.0, 201, 300),
        (209.0, 748.0, 301, 400),
        (748.0, 1000.0, 401, 500),
    ],
    "nh3": [
        (0.0, 200.0, 0, 50),
        (201.0, 400.0, 51, 100),
        (401.0, 800.0, 101, 200),
        (801.0, 1200.0, 201, 300),
        (1201.0, 1800.0, 301, 400),
        (1800.0, 2400.0, 401, 500),
    ],
    "pb": [
        (0.0, 0.5, 0, 50),
        (0.6, 1.0, 51, 100),
        (1.1, 2.0, 101, 200),
        (2.1, 3.0, 201, 300),
        (3.1, 3.5, 301, 400),
        (3.5, 5.0, 401, 500),
    ],
}


def calculate_sub_index(pollutant: str, concentration: float) -> Optional[float]:
    """
    Calculates the CPCB sub-index for a specific pollutant using linear interpolation:
    I = I_low + ((I_high - I_low) / (B_high - B_low)) * (C - B_low)
    """
    if concentration < 0:
        return None

    brackets = BREAKPOINTS.get(pollutant.lower())
    if not brackets:
        return None

    for b_low, b_high, i_low, i_high in brackets:
        if b_low <= concentration <= b_high:
            sub_index = i_low + ((i_high - i_low) / (b_high - b_low)) * (concentration - b_low)
            return round(sub_index, 1)

    # Beyond upper bound (Severe extreme)
    last_bracket = brackets[-1]
    if concentration > last_bracket[1]:
        # Capped or extrapolated at Severe max
        return 500.0

    return None


def get_aqi_category(sub_index: Optional[float]) -> str:
    """Returns the CPCB category label for a given numerical AQI or sub-index."""
    if sub_index is None:
        return "Unavailable"
    
    val = round(sub_index)
    if 0 <= val <= 50:
        return "Good"
    elif 51 <= val <= 100:
        return "Satisfactory"
    elif 101 <= val <= 200:
        return "Moderate"
    elif 201 <= val <= 300:
        return "Poor"
    elif 301 <= val <= 400:
        return "Very Poor"
    else:
        return "Severe"


def evaluate_naqi_from_concentrations(
    pollutants: Dict[str, Optional[PollutantConcentration]],
    has_full_24h_data: bool = False,
    is_model_derived: bool = False
) -> Tuple[Optional[int], str, str, str]:
    """
    Evaluates the overall index and categorizes whether it qualifies as the 
    'official_cpcb_naqi', 'indicative_particulate_subindex', or 'atmospheric_model_estimate'.

    CPCB Minimum Criterion:
    - Minimum of 3 pollutants must be monitored with data-completeness (>=16h for 24h params, >=6h for 8h params).
    - At least one must be PM2.5 or PM10.
    - Model estimates can NEVER be labeled as official CPCB NAQI.

    Returns:
    (index_value, category, index_type, methodology_disclosure)
    """
    valid_sub_indices = {}
    has_particulate = False

    for name, p_data in pollutants.items():
        if p_data and p_data.value is not None:
            sub = calculate_sub_index(name, p_data.value)
            if sub is not None:
                p_data.sub_index = sub
                valid_sub_indices[name] = sub
                if name in ["pm25", "pm10"]:
                    has_particulate = True

    if not valid_sub_indices:
        return (
            None,
            "Unavailable",
            "unavailable",
            "No valid pollutant measurements available to calculate air quality index."
        )

    # Dominant sub-index is the maximum
    max_pollutant, max_sub_index = max(valid_sub_indices.items(), key=lambda item: item[1])
    dominant_index_val = int(round(max_sub_index))
    category = get_aqi_category(dominant_index_val)

    # 1. Model-derived data rule: NEVER official NAQI
    if is_model_derived:
        index_type = "atmospheric_model_estimate"
        disclosure = (
            f"Atmospheric model sub-index estimate ({category}, dominant: {max_pollutant.upper()}) "
            f"derived from ECMWF Copernicus (CAMS) regional reanalysis. "
            f"Ground station telemetry was offline or unavailable for this location."
        )
        return (dominant_index_val, category, index_type, disclosure)

    # 2. Check official CPCB NAQI criteria
    is_official_eligible = (
        len(valid_sub_indices) >= 3 and
        has_particulate and
        has_full_24h_data
    )

    if is_official_eligible:
        index_type = "official_cpcb_naqi"
        disclosure = (
            f"Official Indian National AQI calculated per CPCB methodology across {len(valid_sub_indices)} "
            f"qualifying criteria pollutants with 24-hour completeness. Dominant pollutant: {max_pollutant.upper()}."
        )
    elif has_particulate:
        index_type = "indicative_particulate_subindex"
        disclosure = (
            f"Indicative Real-time Sub-Index calculated using CPCB particulate breakpoints. "
            f"Dominant parameter: {max_pollutant.upper()} ({valid_sub_indices[max_pollutant]} sub-index). "
            f"Official 24h NAQI requires continuous multi-pollutant series with >=16h completeness."
        )
    else:
        index_type = "indicative_particulate_subindex"
        disclosure = (
            f"Indicative gas sub-index ({max_pollutant.upper()}). "
            f"Particulate matter (PM2.5/PM10) was not detected in this observation."
        )

    return (dominant_index_val, category, index_type, disclosure)
