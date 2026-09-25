from dotenv import load_dotenv

from weather_notification.display import print_forecast
from weather_notification.forecast import fetch_rain_forecast
from weather_notification.location import detect_location
from weather_notification.models import RainForecast
from weather_notification.summary import summarize_forecast


def main() -> tuple[RainForecast, str]:
    load_dotenv()
    location = detect_location()
    forecast = fetch_rain_forecast(location, hours=48)
    try:
        summary = summarize_forecast(forecast)
    except Exception as exc:
        summary = f"Could not generate an AI summary: {exc}"
    print_forecast(forecast, summary)
    return forecast, summary
