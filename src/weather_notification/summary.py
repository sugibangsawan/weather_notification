from __future__ import annotations

import os

from openai import OpenAI

from weather_notification.formatting import chance_label, friendly_time
from weather_notification.models import RainForecast


def summarize_forecast(forecast: RainForecast) -> str:
    """Ask OpenAI for a short, practical rain outlook."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing. Add it to your .env file.")

    loc = forecast.location
    wettest = sorted(
        forecast.hours,
        key=lambda hour: hour.rain_mm + hour.showers_mm,
        reverse=True,
    )[:4]
    high_chance = [
        hour
        for hour in forecast.hours
        if hour.probability_percent is not None and hour.probability_percent >= 60
    ]
    facts = [
        "Precomputed facts (trust these over a skim of the table):",
        "Wettest hours by rain+showers mm: "
        + ", ".join(
            f"{friendly_time(hour.time)} "
            f"({hour.rain_mm + hour.showers_mm:.1f}mm, {chance_label(hour.probability_percent)})"
            for hour in wettest
            if hour.rain_mm + hour.showers_mm > 0
        )
        or "none",
        "Hours with chance >= 60%: "
        + ", ".join(
            f"{friendly_time(hour.time)} ({chance_label(hour.probability_percent)}, "
            f"{hour.rain_mm + hour.showers_mm:.1f}mm)"
            for hour in high_chance
        )
        or "none",
    ]
    lines = [
        f"{friendly_time(hour.time)} | "
        f"rain={hour.rain_mm:.1f}mm | showers={hour.showers_mm:.1f}mm | "
        f"chance={chance_label(hour.probability_percent)}"
        for hour in forecast.hours
    ]
    prompt = (
        f"Location: {loc.city}, {loc.region}, {loc.country} ({forecast.timezone})\n"
        + "\n".join(facts)
        + f"\nHourly rain forecast for the next {len(forecast.hours)} hours:\n"
        + "\n".join(lines)
    )

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model="gpt-4o-mini",
        input=[
            {
                "role": "system",
                "content": (
                    "You summarize hourly rain forecasts for a person deciding whether "
                    "to bring an umbrella or change outdoor plans. Write 3-5 short "
                    "sentences. Cover every wet window across the full period, using "
                    "weekday names. Treat millimeters as actual expected rain and "
                    "percent as chance; the wettest hours are those with the most mm, "
                    "not only the highest chance. Mention when it stays dry. "
                    "Do not mention being an AI."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )
    summary = (response.output_text or "").strip()
    if not summary:
        raise RuntimeError("OpenAI returned an empty summary.")
    return summary
