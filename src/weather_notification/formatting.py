from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from weather_notification.models import RainHour


def group_by_day(hours: list[RainHour]) -> list[tuple[str, list[RainHour]]]:
    grouped: dict[str, list[RainHour]] = defaultdict(list)
    order: list[str] = []
    for hour in hours:
        key = datetime.fromisoformat(hour.time).strftime("%A, %b %-d")
        if key not in grouped:
            order.append(key)
        grouped[key].append(hour)
    return [(day, grouped[day]) for day in order]


def format_hour(time_str: str) -> str:
    return datetime.fromisoformat(time_str).strftime("%-I:%M %p")


def friendly_time(time_str: str) -> str:
    return datetime.fromisoformat(time_str).strftime("%A %-I:%M %p")


def chance_label(probability_percent: float | None) -> str:
    if probability_percent is None:
        return "unknown"
    return f"{probability_percent:.0f}%"
