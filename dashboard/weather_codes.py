"""
WMO (World Meteorological Organization) weather-code descriptions used by
Open-Meteo's `current.weather_code` / `daily.weather_code` fields.

Reference: https://open-meteo.com/en/docs (WMO Weather interpretation codes).
"""

_WMO_DESCRIPTIONS: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def describe(code: int) -> str:
    """
    Map a WMO weather code to a human-readable description.

    Args:
        code: WMO weather code as returned by Open-Meteo.

    Returns:
        The description string, or "Unknown" if the code is not recognized.
    """
    return _WMO_DESCRIPTIONS.get(code, "Unknown")
