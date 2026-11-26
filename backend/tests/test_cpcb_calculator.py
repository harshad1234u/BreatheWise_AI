import pytest
from app.services.cpcb_calculator import (
    calculate_sub_index,
    get_aqi_category,
    evaluate_naqi_from_concentrations
)
from app.schemas.air_quality import PollutantConcentration


def test_pm25_sub_index_breakpoints():
    # Good (0-30 -> 0-50)
    assert calculate_sub_index("pm25", 0.0) == 0.0
    assert calculate_sub_index("pm25", 15.0) == 25.0
    assert calculate_sub_index("pm25", 30.0) == 50.0

    # Satisfactory (31-60 -> 51-100)
    sub_sat = calculate_sub_index("pm25", 45.0)
    assert sub_sat is not None
    assert 70.0 <= sub_sat <= 80.0

    # Moderate (61-90 -> 101-200)
    sub_mod = calculate_sub_index("pm25", 75.0)
    assert sub_mod is not None
    assert 140.0 <= sub_mod <= 155.0

    # Poor (91-120 -> 201-300)
    sub_poor = calculate_sub_index("pm25", 105.0)
    assert sub_poor is not None
    assert 240.0 <= sub_poor <= 260.0

    # Very Poor (121-250 -> 301-400)
    sub_vpoor = calculate_sub_index("pm25", 185.0)
    assert sub_vpoor is not None
    assert 340.0 <= sub_vpoor <= 360.0

    # Severe (>250 -> 401-500)
    sub_sev = calculate_sub_index("pm25", 350.0)
    assert sub_sev is not None
    assert 430.0 <= sub_sev <= 460.0


def test_pm10_sub_index_breakpoints():
    # PM10: 0-50 -> 0-50, 51-100 -> 51-100
    assert calculate_sub_index("pm10", 25.0) == 25.0
    assert calculate_sub_index("pm10", 75.0) == 75.0


def test_category_labels():
    assert get_aqi_category(35) == "Good"
    assert get_aqi_category(75) == "Satisfactory"
    assert get_aqi_category(150) == "Moderate"
    assert get_aqi_category(250) == "Poor"
    assert get_aqi_category(350) == "Very Poor"
    assert get_aqi_category(450) == "Severe"
    assert get_aqi_category(None) == "Unavailable"


def test_invalid_negative_concentration():
    assert calculate_sub_index("pm25", -10.0) is None


def test_official_naqi_criteria_met():
    # 3 pollutants including PM2.5, full 24h data
    pollutants = {
        "pm25": PollutantConcentration(value=45.0, unit="µg/m³"),
        "pm10": PollutantConcentration(value=80.0, unit="µg/m³"),
        "no2": PollutantConcentration(value=30.0, unit="µg/m³"),
    }
    index_val, category, index_type, disclosure = evaluate_naqi_from_concentrations(
        pollutants, has_full_24h_data=True
    )
    assert index_val is not None
    assert index_type == "official_cpcb_naqi"
    assert category in ["Good", "Satisfactory", "Moderate"]
    assert "Official Indian National AQI" in disclosure


def test_realtime_indicative_subindex_without_24h_series():
    # Same data but has_full_24h_data is False (e.g., real-time hourly reading)
    pollutants = {
        "pm25": PollutantConcentration(value=150.0, unit="µg/m³"),
        "pm10": PollutantConcentration(value=220.0, unit="µg/m³"),
    }
    index_val, category, index_type, disclosure = evaluate_naqi_from_concentrations(
        pollutants, has_full_24h_data=False
    )
    assert index_val is not None
    assert index_type == "indicative_particulate_subindex"
    assert category in ["Very Poor", "Poor"]
    assert "Indicative Real-time Sub-Index" in disclosure


def test_empty_pollutant_data():
    pollutants = {
        "pm25": None,
        "pm10": None,
    }
    index_val, category, index_type, disclosure = evaluate_naqi_from_concentrations(
        pollutants, has_full_24h_data=False
    )
    assert index_val is None
    assert category == "Unavailable"
    assert index_type == "unavailable"


def test_cpcb_fractional_breakpoint_gaps_pm25_pm10_co_pb():
    """
    Reproduce F-01: fractional concentrations falling between published discrete CPCB
    category integer/decimal thresholds must interpolate monotonically without returning None.
    """
    # PM2.5 gaps: (30,31), (60,61), (90,91), (120,121)
    assert calculate_sub_index("pm25", 30.5) == 50.5
    assert calculate_sub_index("pm25", 60.5) == 100.5
    assert calculate_sub_index("pm25", 90.5) == 200.5
    assert calculate_sub_index("pm25", 120.5) == 300.5

    # PM10 gap: (50,51)
    assert calculate_sub_index("pm10", 50.5) == 50.5

    # CO gap: (1.0, 1.1)
    assert calculate_sub_index("co", 1.05) == 50.5

    # Pb gap: (0.5, 0.6)
    assert calculate_sub_index("pb", 0.55) == 50.5


def test_cpcb_all_eight_pollutants_boundaries_and_invalid_inputs():
    from app.services.cpcb_calculator import BREAKPOINTS

    for pol, brackets in BREAKPOINTS.items():
        # Zero concentration
        assert calculate_sub_index(pol, 0.0) == 0.0
        # Negative concentration -> None
        assert calculate_sub_index(pol, -0.01) is None
        # Exact lower/upper boundaries and immediate neighbors
        for idx, (b_low, b_high, i_low, i_high) in enumerate(brackets):
            low_res = calculate_sub_index(pol, b_low)
            high_res = calculate_sub_index(pol, b_high)
            assert low_res is not None
            assert high_res is not None
            expected_min_low = float(brackets[idx - 1][3]) if (idx > 0 and b_low == brackets[idx - 1][1]) else float(i_low)
            assert expected_min_low - 0.1 <= low_res <= float(i_high) + 0.1
            if idx + 1 < len(brackets):
                next_low = brackets[idx + 1][0]
                if next_low > b_high:
                    mid = (b_high + next_low) / 2.0
                    mid_res = calculate_sub_index(pol, mid)
                    assert mid_res is not None
                    assert high_res <= mid_res <= calculate_sub_index(pol, next_low)
                else:
                    above_border = calculate_sub_index(pol, b_high + 0.01)
                    assert above_border is not None and above_border >= 401.0
            if b_high > b_low:
                below_high = calculate_sub_index(pol, b_high - 0.01)
                assert below_high is not None and below_high <= high_res
        # Above maximum published breakpoint -> capped at 500.0
        max_b = brackets[-1][1]
        assert calculate_sub_index(pol, max_b + 50.0) == 500.0

    # Non-finite values must not fabricate sub-indices
    assert calculate_sub_index("pm25", float("nan")) is None
    assert calculate_sub_index("pm25", float("inf")) is None
