import os
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from dotenv import load_dotenv

from weather_notification import main
from weather_notification.email_content import html_body, place_name, plain_body
from weather_notification.models import RainForecast


def send_forecast_email(forecast: RainForecast, summary: str) -> None:
    sender = os.getenv("SENDER_EMAIL")
    receiver = os.getenv("RECEIVER_EMAIL")
    password = os.getenv("GMAIL_APP_PASS") or ""
    if not sender or not receiver or not password:
        raise RuntimeError(
            "SENDER_EMAIL, RECEIVER_EMAIL, and GMAIL_APP_PASS must be set in .env"
        )

    place = place_name(forecast)
    message = EmailMessage()
    message["Subject"] = f"Rain forecast — {place or 'your location'}"
    message["From"] = sender
    message["To"] = receiver
    message.set_content(plain_body(forecast, summary))
    message.add_alternative(html_body(forecast, summary), subtype="html")

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as smtp:
        smtp.starttls()
        smtp.login(sender, password)
        smtp.send_message(message)


if __name__ == "__main__":
    load_dotenv(Path(__file__).resolve().parent / ".env")
    forecast, summary = main()
    send_forecast_email(forecast, summary)
    print("Forecast emailed.")
