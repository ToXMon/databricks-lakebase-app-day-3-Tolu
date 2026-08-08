"""
Focused tests for the deterministic recommendation logic in
weather_mcp_server._build_recommendation / get_weather_recommendation.
"""

from mcp_server import weather_mcp_server


def test_t19_facts_used_lists_every_observed_field():
    day = {
        "date": "2026-08-09",
        "weather_code": 61,
        "weather_description": "Slight rain",
        "temperature_2m_max": 20.0,
        "temperature_2m_min": 15.0,
        "precipitation_sum": 3.2,
        "precipitation_probability_max": 55,
        "wind_speed_10m_max": 20.0,
    }
    rec = weather_mcp_server._build_recommendation(day, activity=None)
    fact_names = {f["name"] for f in rec["facts_used"]}
    assert fact_names == {
        "precipitation_probability_max",
        "precipitation_sum",
        "temperature_2m_max",
        "wind_speed_10m_max",
        "weather_code",
    }
    for fact in rec["facts_used"]:
        assert "value" in fact
        assert "threshold" in fact


def test_t20_thunderstorm_weather_code_triggers_travel_caution():
    day = {
        "date": "2026-08-09",
        "weather_code": 95,
        "weather_description": "Thunderstorm",
        "temperature_2m_max": 26.0,
        "temperature_2m_min": 22.0,
        "precipitation_sum": 12.5,
        "precipitation_probability_max": 90,
        "wind_speed_10m_max": 10.0,  # low wind, but thunderstorm code should still force caution
    }
    rec = weather_mcp_server._build_recommendation(day, activity=None)
    assert rec["travel"]["advice"] == "travel with caution"
    assert any("thunderstorm" in r.lower() or "95" in r for r in rec["travel"]["reasons"])
