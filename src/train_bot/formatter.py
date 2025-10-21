from __future__ import annotations

import datetime as dt
from typing import Sequence

from .transport_api import Departure


def format_departures(
    origin_name: str,
    destination_name: str | None,
    departures: Sequence[Departure],
    *,
    requested_time: dt.datetime | None = None,
) -> str:
    """Render a text summary of departures for Telegram."""

    if not departures:
        header = _format_header(origin_name, destination_name, requested_time)
        return f"{header}\nNo matching services found."

    lines = [_format_header(origin_name, destination_name, requested_time)]
    for idx, service in enumerate(departures, start=1):
        destination = destination_name or service.destination_name
        timing = _format_timing(service)
        platform = f"Platform {service.platform}" if service.platform else "Platform TBC"
        operator = service.operator_name or service.service
        calling_points = _format_calling_points(service)
        lines.append(
            "\n".join(
                [
                    f"{idx}. {origin_name} ➜ {destination}",
                    timing,
                    platform,
                    f"Operator: {operator}",
                    calling_points,
                ]
            )
        )

    return "\n\n".join(lines)


def _format_header(
    origin_name: str,
    destination_name: str | None,
    requested_time: dt.datetime | None,
) -> str:
    if destination_name:
        base = f"Next services from {origin_name} to {destination_name}"
    else:
        base = f"Next services departing {origin_name}"

    if not requested_time:
        return base

    return f"{base} after {requested_time.strftime('%H:%M on %d %b')}"


def _format_timing(service: Departure) -> str:
    expected = service.expected_departure_time
    aimed = service.aimed_departure_time
    status = service.status
    if expected and expected != aimed:
        return f"Due {aimed} (est. {expected}, {status})"
    return f"Due {aimed} ({status})"


def _format_calling_points(service: Departure) -> str:
    if not service.calling_points:
        return "Calling points data unavailable."

    points = [point.station_name for point in service.calling_points]
    return "Calling at: " + ", ".join(points[:6]) + ("…" if len(points) > 6 else "")
