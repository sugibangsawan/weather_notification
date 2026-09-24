from __future__ import annotations

import json
import urllib.error
import urllib.request


def get_json(url: str, timeout: float) -> dict:
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
