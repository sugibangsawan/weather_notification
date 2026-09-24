from __future__ import annotations

import json
import urllib.error

from weather_notification.http import get_json
from weather_notification.models import Location


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


def _from_ipwho(timeout: float) -> Location:
    data = get_json("https://ipwho.is/", timeout)
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
    data = get_json(
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
