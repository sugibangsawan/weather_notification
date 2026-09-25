import os
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from dotenv import load_dotenv

from weather_notification import main
from weather_notification.formatting import chance_label, format_hour, group_by_day
from weather_notification.models import RainForecast


def send_forecast_email(forecast: RainForecast, summary: str) -> None:
    sender = os.getenv("SENDER_EMAIL")
    receiver = os.getenv("RECEIVER_EMAIL")
    password = os.getenv("GMAIL_APP_PASS") or ""
    if not sender or not receiver or not password:
        raise RuntimeError(
            "SENDER_EMAIL, RECEIVER_EMAIL, and GMAIL_APP_PASS must be set in .env"
        )

    loc = forecast.location
    place = ", ".join(part for part in (loc.city, loc.region, loc.country) if part)
    subject = f"Rain forecast — {place or 'your location'}"

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = receiver
    message.set_content(_email_body(forecast, summary, place))

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as smtp:
        smtp.starttls()
        smtp.login(sender, password)
        smtp.send_message(message)


def _email_body(forecast: RainForecast, summary: str, place: str) -> str:
    loc = forecast.location
    lines = [
        f"Rain forecast — {place or 'Unknown location'}",
        f"{loc.latitude:.2f}, {loc.longitude:.2f}  ·  "
        f"next {len(forecast.hours)} hours  ·  {forecast.timezone}",
        "",
        "AI outlook",
        summary,
        "",
    ]
    for day_label, hours in group_by_day(forecast.hours):
        lines.append(day_label)
        lines.append(f"{'Time':<10} {'Rain':>8} {'Showers':>8} {'Chance':>8}  Outlook")
        for hour in hours:
            total = hour.rain_mm + hour.showers_mm
            rain = f"{hour.rain_mm:.1f}mm" if hour.rain_mm > 0 else "—"
            showers = f"{hour.showers_mm:.1f}mm" if hour.showers_mm > 0 else "—"
            chance = chance_label(hour.probability_percent)
            if chance != "unknown":
                chance = chance
            lines.append(
                f"{format_hour(hour.time):<10} {rain:>8} {showers:>8} {chance:>8}  "
                f"{_outlook_label(total, hour.probability_percent)}"
            )
        lines.append("")
    return "\n".join(lines)


def _outlook_label(total_mm: float, probability_percent: float | None) -> str:
    chance = probability_percent or 0
    if total_mm >= 2.5 or chance >= 80:
        return "Heavy rain likely"
    if total_mm >= 0.5 or chance >= 60:
        return "Rain likely"
    if total_mm > 0 or chance >= 40:
        return "Possible showers"
    return "Dry"


if __name__ == "__main__":
    load_dotenv(Path(__file__).resolve().parent / ".env")
    forecast, summary = main()
    send_forecast_email(forecast, summary)
    print("Forecast emailed.")
