from __future__ import annotations

import json
import subprocess
import tempfile
import urllib.error
import urllib.parse
from pathlib import Path

from rich.console import Console

from weather_notification.http import get_json
from weather_notification.models import Location

REVERSE_GEOCODE_URL = "https://nominatim.openstreetmap.org/reverse"
GENERIC_REGIONS = {
    "java",
    "jawa",
    "sumatra",
    "sumatera",
    "kalimantan",
    "sulawesi",
    "papua",
    "bali",
    "maluku",
}


def detect_location(timeout: float = 20.0) -> Location:
    """Detect this device's location from GPS / Core Location.

    Falls back to public-IP geolocation if Location Services are unavailable.
    """
    errors: list[str] = []

    try:
        return refine_location(_from_gps(timeout), timeout=min(timeout, 8.0))
    except (RuntimeError, FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        errors.append(f"gps: {exc}")
        Console().print(
            f"[yellow]GPS unavailable:[/yellow] {exc}\n"
            "[dim]Enable Weather Notification in System Settings > Privacy & Security > Location Services, then run again.[/dim]"
        )

    for fetcher in (_from_ipwho, _from_ip_api):
        try:
            return refine_location(fetcher(min(timeout, 5.0)), min(timeout, 5.0))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, RuntimeError) as exc:
            errors.append(f"{fetcher.__name__}: {exc}")

    raise RuntimeError("Could not detect location. " + " | ".join(errors))


def refine_location(location: Location, timeout: float = 5.0) -> Location:
    """Turn coordinates into a neighborhood / city label."""
    try:
        query = urllib.parse.urlencode(
            {
                "lat": location.latitude,
                "lon": location.longitude,
                "format": "json",
                "addressdetails": 1,
                "zoom": 16,
            }
        )
        data = get_json(f"{REVERSE_GEOCODE_URL}?{query}", timeout)
        addr = data.get("address") or {}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, RuntimeError):
        return location

    village = _addr(addr, "village", "neighbourhood", "quarter", "hamlet")
    suburb = _addr(addr, "suburb")
    city_district = _addr(addr, "city_district", "municipality", "county")
    city = _addr(addr, "city", "town") or location.city
    if suburb and city_district:
        district = suburb
        if city_district.casefold() != city.casefold():
            city = city_district
    else:
        district = suburb or city_district

    parts: list[str] = []
    for part in (village, district, city, _addr(addr, "state", "region") or location.region):
        cleaned = part.strip()
        if not cleaned:
            continue
        if cleaned.casefold() in GENERIC_REGIONS and any(parts):
            continue
        if any(cleaned.casefold() == existing.casefold() for existing in parts):
            continue
        parts.append(cleaned)

    return Location(
        latitude=location.latitude,
        longitude=location.longitude,
        city=parts[0] if parts else location.city,
        region=_region_from_parts(parts, location.region),
        country=_addr(addr, "country") or location.country,
        ip=location.ip,
        source=f"{location.source}+nominatim",
    )


def _from_gps(timeout: float = 30.0) -> Location:
    app = _gps_app()
    output = Path(tempfile.mkdtemp()) / "coords.txt"
    Console().print(
        "[cyan]Asking this Mac for GPS via Weather Notification...[/cyan]\n"
        "[dim]Click Allow if macOS asks. Then enable Weather Notification in Location Services.[/dim]"
    )
    try:
        result = subprocess.run(
            ["open", "-W", "-n", str(app), "--args", str(output)],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "GPS timed out. Enable Weather Notification in System Settings > "
            "Privacy & Security > Location Services, then run again."
        ) from exc

    text = output.read_text().strip() if output.exists() else ""
    if text.startswith("ERROR:"):
        raise RuntimeError(text.removeprefix("ERROR:").strip())
    if result.returncode != 0 and not text:
        raise RuntimeError((result.stderr or "GPS lookup failed").strip())

    parts = text.split(",")
    if len(parts) < 2:
        raise RuntimeError(
            "GPS did not return coordinates. After the first run, "
            "Weather Notification should appear in System Settings > Privacy & Security > "
            "Location Services. Turn it on, then run again."
        )

    return Location(
        latitude=float(parts[0]),
        longitude=float(parts[1]),
        city="",
        region="",
        country="",
        ip="",
        source="gps",
    )


def _gps_app() -> Path:
    root = Path(__file__).resolve().parents[2]
    source = root / "location_helper.swift"
    plist = root / "LocationInfo.plist"
    app = root / "Weather Notification.app"
    binary = app / "Contents" / "MacOS" / "Weather Notification"
    bundled_plist = app / "Contents" / "Info.plist"
    if not source.exists() or not plist.exists():
        raise RuntimeError("GPS helper source is missing.")

    if (
        binary.exists()
        and bundled_plist.exists()
        and binary.stat().st_mtime >= source.stat().st_mtime
        and bundled_plist.stat().st_mtime >= plist.stat().st_mtime
    ):
        return app

    binary.parent.mkdir(parents=True, exist_ok=True)
    bundled_plist.write_bytes(plist.read_bytes())
    compiled = subprocess.run(
        [
            "swiftc",
            "-O",
            str(source),
            "-o",
            str(binary),
            "-framework",
            "AppKit",
            "-framework",
            "CoreLocation",
        ],
        capture_output=True,
        text=True,
    )
    if compiled.returncode != 0:
        raise RuntimeError((compiled.stderr or compiled.stdout or "swiftc failed").strip())
    subprocess.run(
        ["codesign", "--force", "--deep", "--sign", "-", str(app)],
        capture_output=True,
        text=True,
        check=False,
    )
    return app


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


def _region_from_parts(parts: list[str], fallback: str) -> str:
    if len(parts) > 1:
        return ", ".join(parts[1:])
    if fallback and fallback.casefold() not in GENERIC_REGIONS:
        return fallback
    return ""


def _addr(addr: dict, *keys: str) -> str:
    for key in keys:
        value = addr.get(key)
        if value:
            return str(value)
    return ""
