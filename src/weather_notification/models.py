from __future__ import annotations

from dataclasses import dataclass


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
