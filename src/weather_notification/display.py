from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from weather_notification.formatting import format_hour, group_by_day
from weather_notification.models import RainForecast


def print_forecast(forecast: RainForecast, summary: str | None = None) -> None:
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

    for day_label, hours in group_by_day(forecast.hours):
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
                format_hour(hour.time),
                _styled_mm(hour.rain_mm),
                _styled_mm(hour.showers_mm),
                _styled_chance(hour.probability_percent),
                _outlook(total, hour.probability_percent),
            )
        console.print(table)
        console.print()


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
