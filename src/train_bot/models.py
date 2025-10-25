from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence


@dataclass(frozen=True)
class CallingPoint:
    station_name: str
    station_code: str
    aimed_arrival_time: Optional[str]
    expected_arrival_time: Optional[str]


@dataclass(frozen=True)
class Departure:
    service_uid: str
    destination_name: str
    destination_code: str
    platform: Optional[str]
    aimed_departure_time: Optional[str]
    expected_departure_time: Optional[str]
    status: str
    calling_points: Sequence[CallingPoint]
    operator_name: Optional[str]


@dataclass(frozen=True)
class StationSummary:
    name: str
    station_code: str
