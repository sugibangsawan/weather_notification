from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


@dataclass(frozen=True)
class Location:
    latitude: float
    longitude: float
    city: str
    region: str
    country: str
    ip: str
    source: str


@dataclass(frozen=True)
class RainHour:
    time: str
    rain_mm: float
    showers_mm: float
    probability_percent: float | None


@dataclass(frozen=True)
class RainForecast:
    location: Location
    timezone: str
    hours: list[RainHour]


def detect_location(timeout: float = 5.0) -> Location:
    """Detect this device's approximate location from its public IP.

    City-level accuracy is typical. Requires an internet connection.
    """
    errors: list[str] = []

    for fetcher in (_from_ipwho, _from_ip_api):
        try:
            return fetcher(timeout)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, RuntimeError) as exc:
            errors.append(f"{fetcher.__name__}: {exc}")

    raise RuntimeError("Could not detect location. " + " | ".join(errors))


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
    data = _get_json(f"{FORECAST_URL}?{query}", timeout)
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
    


def _from_ipwho(timeout: float) -> Location:
    data = _get_json("https://ipwho.is/", timeout)
    if not data.get("success", False):
        raise RuntimeError(data.get("message", "ipwho.is lookup failed"))

    return Location(
        latitude=float(data["latitude"]),
        longitude=float(data["longitude"]),
        city=str(data.get("city") or ""),
        region=str(data.get("region") or ""),
        country=str(data.get("country") or ""),
        ip=str(data.get("ip") or ""),
        source="ipwho.is",
    )


def _from_ip_api(timeout: float) -> Location:
    data = _get_json(
        "http://ip-api.com/json/?fields=status,message,country,regionName,city,lat,lon,query",
        timeout,
    )
    if data.get("status") != "success":
        raise RuntimeError(data.get("message", "ip-api lookup failed"))

    return Location(
        latitude=float(data["lat"]),
        longitude=float(data["lon"]),
        city=str(data.get("city") or ""),
        region=str(data.get("regionName") or ""),
        country=str(data.get("country") or ""),
        ip=str(data.get("query") or ""),
        source="ip-api.com",
    )


def _get_json(url: str, timeout: float) -> dict:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "weather-notification"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
        if payload.get("error"):
            raise RuntimeError(payload.get("reason", body)) from exc
        raise


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
            f"{_friendly_time(hour.time)} "
            f"({hour.rain_mm + hour.showers_mm:.1f}mm, {_chance_label(hour.probability_percent)})"
            for hour in wettest
            if hour.rain_mm + hour.showers_mm > 0
        )
        or "none",
        "Hours with chance >= 60%: "
        + ", ".join(
            f"{_friendly_time(hour.time)} ({_chance_label(hour.probability_percent)}, "
            f"{hour.rain_mm + hour.showers_mm:.1f}mm)"
            for hour in high_chance
        )
        or "none",
    ]
    lines = [
        f"{_friendly_time(hour.time)} | "
        f"rain={hour.rain_mm:.1f}mm | showers={hour.showers_mm:.1f}mm | "
        f"chance={_chance_label(hour.probability_percent)}"
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


def _print_forecast(forecast: RainForecast, summary: str | None = None) -> None:
    console = Console()
    loc = forecast.location
    place = ", ".join(part for part in (loc.city, loc.region, loc.country) if part)
    header = Text()
    header.append("Rain forecast\n", style="bold white")
    header.append(place or "Unknown location", style="bold cyan")
    header.append(
        f"\n{loc.latitude:.2f}, {loc.longitude:.2f}  ·  "
        f"next {len(forecast.hours)} hours  ·  {forecast.timezone}",
        style="dim",
    )
    console.print(Panel(header, border_style="cyan", padding=(1, 2)))

    if summary:
        console.print(
            Panel(
                summary,
                title="[bold]AI outlook[/bold]",
                border_style="magenta",
                padding=(1, 2),
            )
        )

    for day_label, hours in _group_by_day(forecast.hours):
        table = Table(
            title=day_label,
            title_style="bold",
            header_style="bold",
            border_style="bright_black",
            show_lines=False,
            pad_edge=False,
        )
        table.add_column("Time", style="white", no_wrap=True)
        table.add_column("Rain", justify="right")
        table.add_column("Showers", justify="right")
        table.add_column("Chance", justify="right")
        table.add_column("Outlook", min_width=14)

        for hour in hours:
            total = hour.rain_mm + hour.showers_mm
            table.add_row(
                _format_hour(hour.time),
                _styled_mm(hour.rain_mm),
                _styled_mm(hour.showers_mm),
                _styled_chance(hour.probability_percent),
                _outlook(total, hour.probability_percent),
            )
        console.print(table)
        console.print()


def _group_by_day(hours: list[RainHour]) -> list[tuple[str, list[RainHour]]]:
    grouped: dict[str, list[RainHour]] = defaultdict(list)
    order: list[str] = []
    for hour in hours:
        key = datetime.fromisoformat(hour.time).strftime("%A, %b %-d")
        if key not in grouped:
            order.append(key)
        grouped[key].append(hour)
    return [(day, grouped[day]) for day in order]


def _format_hour(time_str: str) -> str:
    return datetime.fromisoformat(time_str).strftime("%-I:%M %p")


def _friendly_time(time_str: str) -> str:
    return datetime.fromisoformat(time_str).strftime("%A %-I:%M %p")


def _chance_label(probability_percent: float | None) -> str:
    if probability_percent is None:
        return "unknown"
    return f"{probability_percent:.0f}%"


def _styled_mm(amount: float) -> Text:
    label = f"{amount:.1f} mm"
    if amount >= 2.5:
        return Text(label, style="bold blue")
    if amount >= 0.5:
        return Text(label, style="cyan")
    if amount > 0:
        return Text(label, style="dim cyan")
    return Text("—", style="dim")


def _styled_chance(probability_percent: float | None) -> Text:
    if probability_percent is None:
        return Text("—", style="dim")
    filled = round(probability_percent / 10)
    bar = "█" * filled + "░" * (10 - filled)
    if probability_percent >= 70:
        style = "bold red"
    elif probability_percent >= 40:
        style = "yellow"
    else:
        style = "green"
    return Text(f"{bar} {probability_percent:.0f}%", style=style)


def _outlook(total_mm: float, probability_percent: float | None) -> Text:
    chance = probability_percent or 0
    if total_mm >= 2.5 or chance >= 80:
        return Text("Heavy rain likely", style="bold blue")
    if total_mm >= 0.5 or chance >= 60:
        return Text("Rain likely", style="cyan")
    if total_mm > 0 or chance >= 40:
        return Text("Possible showers", style="yellow")
    return Text("Dry", style="dim")


if __name__ == "__main__":
    load_dotenv(Path(__file__).resolve().parent / ".env")
    location = detect_location()
    forecast = fetch_rain_forecast(location, hours=48)
    try:
        summary = summarize_forecast(forecast)
    except Exception as exc:
        summary = f"Could not generate an AI summary: {exc}"
    _print_forecast(forecast, summary)
