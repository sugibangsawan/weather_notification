from __future__ import annotations

import urllib.parse

from weather_notification.http import get_json
from weather_notification.models import Location, RainForecast, RainHour

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def fetch_rain_forecast(
    location: Location,
    hours: int = 48,
    timeout: float = 10.0,
) -> RainForecast:
    """Fetch hourly rain from this hour through the next `hours` hours."""
    query = urllib.parse.urlencode(
        {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "hourly": "rain,showers,precipitation_probability",
            "forecast_hours": hours,
            "timezone": "auto",
        }
    )
    data = get_json(f"{FORECAST_URL}?{query}", timeout)
    hourly = data["hourly"]
    times = hourly["time"]
    rain = hourly["rain"]
    showers = hourly["showers"]
    probability = hourly.get("precipitation_probability") or [None] * len(times)

    return RainForecast(
        location=location,
        timezone=str(data.get("timezone") or "auto"),
        hours=[
            RainHour(
                time=str(times[i]),
                rain_mm=float(rain[i] or 0.0),
                showers_mm=float(showers[i] or 0.0),
                probability_percent=(
                    None if probability[i] is None else float(probability[i])
                ),
            )
            for i in range(len(times))
        ],
    )
