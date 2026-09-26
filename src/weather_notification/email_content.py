from __future__ import annotations

from html import escape

from weather_notification.formatting import chance_label, format_hour, friendly_time, group_by_day
from weather_notification.models import RainForecast, RainHour


def place_name(forecast: RainForecast) -> str:
    loc = forecast.location
    return ", ".join(part for part in (loc.city, loc.region, loc.country) if part)


def plain_body(forecast: RainForecast, summary: str) -> str:
    loc = forecast.location
    place = place_name(forecast)
    highlights = _highlights(forecast)
    lines = [
        f"Rain forecast — {place or 'Unknown location'}",
        f"{loc.latitude:.6f}, {loc.longitude:.6f}  ·  "
        f"{'GPS' if loc.source.startswith('gps') else 'IP location'}  ·  "
        f"next {len(forecast.hours)} hours  ·  {forecast.timezone}",
        "",
        "Highlights",
        f"- Bring an umbrella: {highlights['umbrella']}",
        f"- Wettest hour: {highlights['wettest']}",
        f"- Highest rain chance: {highlights['highest_chance']}",
        f"- Expected rain (48h): {highlights['total_rain']}",
        "",
        "AI outlook",
        summary,
        "",
    ]
    for day_label, hours in group_by_day(forecast.hours):
        lines.append(day_label)
        lines.append(
            f"{'Time':<10} {'Rain':>8} {'Showers':>8} {'Total':>8} {'Chance':>8}  Outlook"
        )
        for hour in hours:
            total = hour.rain_mm + hour.showers_mm
            lines.append(
                f"{format_hour(hour.time):<10} "
                f"{_mm(hour.rain_mm):>8} "
                f"{_mm(hour.showers_mm):>8} "
                f"{_mm(total):>8} "
                f"{_chance_text(hour.probability_percent):>8}  "
                f"{outlook_label(total, hour.probability_percent)}"
            )
        lines.append("")
    return "\n".join(lines)


def html_body(forecast: RainForecast, summary: str) -> str:
    loc = forecast.location
    place = place_name(forecast) or "Unknown location"
    highlights = _highlights(forecast)
    day_sections = "".join(
        _day_table(day_label, hours) for day_label, hours in group_by_day(forecast.hours)
    )
    return f"""<!DOCTYPE html>
<html>
  <body style="margin:0;padding:0;background:#eef2f6;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#eef2f6;padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="640" cellpadding="0" cellspacing="0" style="width:640px;max-width:100%;background:#ffffff;border-radius:16px;overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#1f2937;">
            <tr>
              <td style="background:#0f766e;color:#ffffff;padding:28px 28px 22px;">
                <div style="font-size:13px;letter-spacing:0.08em;text-transform:uppercase;opacity:0.85;">48-hour rain forecast</div>
                <div style="font-size:26px;font-weight:700;margin-top:6px;">{escape(place)}</div>
                <div style="font-size:13px;margin-top:8px;opacity:0.9;">
                  {loc.latitude:.6f}, {loc.longitude:.6f} · {'GPS' if loc.source.startswith('gps') else 'IP location'} · {escape(forecast.timezone)} · next {len(forecast.hours)} hours
                </div>
              </td>
            </tr>
            <tr>
              <td style="padding:20px 28px 8px;">
                {_stat_row(highlights)}
              </td>
            </tr>
            <tr>
              <td style="padding:8px 28px 20px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f5f3ff;border-radius:12px;">
                  <tr>
                    <td style="padding:16px 18px;">
                      <div style="font-size:12px;font-weight:700;color:#6d28d9;letter-spacing:0.06em;text-transform:uppercase;">AI outlook</div>
                      <div style="font-size:15px;line-height:1.55;margin-top:8px;color:#1f2937;">{escape(summary)}</div>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            {day_sections}
            <tr>
              <td style="padding:8px 28px 24px;font-size:12px;color:#6b7280;line-height:1.5;">
                Rain is large-scale rainfall. Showers are convective rain. Totals are millimeters for that hour.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""


def outlook_label(total_mm: float, probability_percent: float | None) -> str:
    chance = probability_percent or 0
    if total_mm >= 2.5 or chance >= 80:
        return "Heavy rain likely"
    if total_mm >= 0.5 or chance >= 60:
        return "Rain likely"
    if total_mm > 0 or chance >= 40:
        return "Possible showers"
    return "Dry"


def _highlights(forecast: RainForecast) -> dict[str, str]:
    hours = forecast.hours
    wettest = max(hours, key=lambda hour: hour.rain_mm + hour.showers_mm)
    highest = max(
        hours,
        key=lambda hour: hour.probability_percent or 0,
    )
    total = sum(hour.rain_mm + hour.showers_mm for hour in hours)
    wet_hours = [
        hour
        for hour in hours
        if (hour.probability_percent or 0) >= 60 or hour.rain_mm + hour.showers_mm > 0
    ]
    if wet_hours:
        first = wet_hours[0]
        last = wet_hours[-1]
        umbrella = (
            f"{friendly_time(first.time)} to {friendly_time(last.time)}"
            if first.time != last.time
            else friendly_time(first.time)
        )
    else:
        umbrella = "Not needed — little rain expected"

    wettest_total = wettest.rain_mm + wettest.showers_mm
    wettest_text = (
        f"{friendly_time(wettest.time)} · {wettest_total:.1f} mm"
        if wettest_total > 0
        else "No measurable rain"
    )
    return {
        "umbrella": umbrella,
        "wettest": wettest_text,
        "highest_chance": f"{friendly_time(highest.time)} · {_chance_text(highest.probability_percent)}",
        "total_rain": f"{total:.1f} mm",
    }


def _stat_row(highlights: dict[str, str]) -> str:
    cards = [
        ("Umbrella", highlights["umbrella"]),
        ("Wettest hour", highlights["wettest"]),
        ("Highest chance", highlights["highest_chance"]),
        ("48h total", highlights["total_rain"]),
    ]
    cells = []
    for title, value in cards:
        cells.append(
            f"""<td width="25%" valign="top" style="padding:6px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;border:1px solid #e5e7eb;border-radius:10px;">
                <tr>
                  <td style="padding:12px;">
                    <div style="font-size:11px;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:0.05em;">{escape(title)}</div>
                    <div style="font-size:13px;font-weight:600;margin-top:6px;color:#111827;line-height:1.4;">{escape(value)}</div>
                  </td>
                </tr>
              </table>
            </td>"""
        )
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>{"".join(cells)}</tr></table>'


def _day_table(day_label: str, hours: list[RainHour]) -> str:
    rows = "".join(_hour_row(hour, index) for index, hour in enumerate(hours))
    return f"""
            <tr>
              <td style="padding:4px 28px 20px;">
                <div style="font-size:16px;font-weight:700;margin:0 0 10px;">{escape(day_label)}</div>
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;font-size:13px;">
                  <tr style="background:#f1f5f9;color:#475569;">
                    <th align="left" style="padding:8px 10px;border-bottom:1px solid #e2e8f0;">Time</th>
                    <th align="right" style="padding:8px 10px;border-bottom:1px solid #e2e8f0;">Rain</th>
                    <th align="right" style="padding:8px 10px;border-bottom:1px solid #e2e8f0;">Showers</th>
                    <th align="right" style="padding:8px 10px;border-bottom:1px solid #e2e8f0;">Total</th>
                    <th align="right" style="padding:8px 10px;border-bottom:1px solid #e2e8f0;">Chance</th>
                    <th align="left" style="padding:8px 10px;border-bottom:1px solid #e2e8f0;">Outlook</th>
                  </tr>
                  {rows}
                </table>
              </td>
            </tr>
"""


def _hour_row(hour: RainHour, index: int) -> str:
    total = hour.rain_mm + hour.showers_mm
    label = outlook_label(total, hour.probability_percent)
    color, background = _outlook_colors(label)
    stripe = "#ffffff" if index % 2 == 0 else "#f8fafc"
    row_bg = background if label != "Dry" else stripe
    return (
        f'<tr style="background:{row_bg};">'
        f'<td style="padding:8px 10px;border-bottom:1px solid #eef2f7;">{escape(format_hour(hour.time))}</td>'
        f'<td align="right" style="padding:8px 10px;border-bottom:1px solid #eef2f7;">{escape(_mm(hour.rain_mm))}</td>'
        f'<td align="right" style="padding:8px 10px;border-bottom:1px solid #eef2f7;">{escape(_mm(hour.showers_mm))}</td>'
        f'<td align="right" style="padding:8px 10px;border-bottom:1px solid #eef2f7;font-weight:600;">{escape(_mm(total))}</td>'
        f'<td align="right" style="padding:8px 10px;border-bottom:1px solid #eef2f7;">{_chance_bar(hour.probability_percent)}</td>'
        f'<td style="padding:8px 10px;border-bottom:1px solid #eef2f7;color:{color};font-weight:600;">{escape(label)}</td>'
        f"</tr>"
    )


def _outlook_colors(label: str) -> tuple[str, str]:
    if label == "Heavy rain likely":
        return "#1d4ed8", "#dbeafe"
    if label == "Rain likely":
        return "#0f766e", "#ccfbf1"
    if label == "Possible showers":
        return "#b45309", "#fef3c7"
    return "#6b7280", "#ffffff"


def _chance_bar(probability_percent: float | None) -> str:
    if probability_percent is None:
        return "—"
    filled = max(0, min(10, round(probability_percent / 10)))
    bar = "●" * filled + "○" * (10 - filled)
    if probability_percent >= 70:
        color = "#dc2626"
    elif probability_percent >= 40:
        color = "#d97706"
    else:
        color = "#16a34a"
    return (
        f'<span style="color:{color};letter-spacing:1px;font-size:11px;">{bar}</span>'
        f' <span style="font-weight:600;">{probability_percent:.0f}%</span>'
    )


def _mm(amount: float) -> str:
    if amount <= 0:
        return "—"
    return f"{amount:.1f} mm"


def _chance_text(probability_percent: float | None) -> str:
    if probability_percent is None:
        return "—"
    return chance_label(probability_percent)
