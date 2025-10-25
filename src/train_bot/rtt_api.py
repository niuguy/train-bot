from __future__ import annotations

import datetime as dt
from typing import Any, Optional, Sequence
from urllib.parse import quote

import httpx

from .config import RttSettings
from .models import CallingPoint, Departure, StationSummary


class RttError(RuntimeError):
    """Raised when the RealTimeTrains API returns an error."""


class RttClient:
    """Async client for interacting with the RealTimeTrains public API."""

    def __init__(self, settings: RttSettings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.base_url,
            timeout=10.0,
            headers={"Accept": "application/json"},
            follow_redirects=True,
            auth=httpx.BasicAuth(settings.username, settings.password),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "RttClient":  # pragma: no cover - convenience
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - convenience
        await self.close()

    async def search_station(self, query: str, *, limit: int = 5) -> Sequence[StationSummary]:
        """Return best matching stations for a user provided query."""

        path = f"/api/v1/json/search/{quote(query, safe='')}"
        response = await self._client.get(path)
        payload = await self._json_or_error(response, "searching for stations")

        locations = payload.get("locations", [])
        matches: list[StationSummary] = []
        for item in locations:
            code = item.get("crs")
            name = item.get("name") or item.get("description", "")
            if not code or not name:
                continue
            matches.append(StationSummary(name=name, station_code=code))
            if len(matches) >= limit:
                break
        return matches

    async def get_departures(
        self,
        origin_crs: str,
        *,
        destination_crs: Optional[str] = None,
        limit: int = 5,
        when: Optional[dt.datetime] = None,
    ) -> Sequence[Departure]:
        """Return upcoming departures from origin, optionally filtered by destination."""

        origin = origin_crs.upper()
        destination = (destination_crs or "").upper()
        if not destination:
            path = f"/api/v1/json/dep/{origin}"
        else:
            path = f"/api/v1/json/search/{origin}/to/{destination}"

        response = await self._client.get(path)
        payload = await self._json_or_error(response, "requesting departures")

        services = payload.get("services", [])
        departures: list[Departure] = []
        for service in services:
            detail = service.get("locationDetail") or {}
            aimed = detail.get("gbttBookedDeparture")
            expected = detail.get("realtimeDeparture") or detail.get("gbttBookedDeparture")
            run_date = service.get("runDate")

            if when and run_date and aimed:
                try:
                    run_dt = dt.datetime.strptime(f"{run_date} {aimed}", "%Y-%m-%d %H:%M")
                except ValueError:
                    run_dt = None
                if run_dt and run_dt < when:
                    continue

            destination_info = self._select_destination(detail)
            calling_points = self._parse_calling_points(detail)
            status = self._derive_status(detail)

            departures.append(
                Departure(
                    service_uid=service.get("serviceUid", ""),
                    destination_name=destination_info[0],
                    destination_code=destination_info[1],
                    platform=detail.get("platform"),
                    aimed_departure_time=aimed,
                    expected_departure_time=expected,
                    status=status,
                    calling_points=calling_points,
                    operator_name=service.get("atocName") or service.get("atocCode"),
                )
            )

        return departures[:limit]

    async def _json_or_error(self, response: httpx.Response, action: str) -> dict[str, Any]:
        if response.status_code >= 400:
            raise RttError(
                f"RealTimeTrains error {response.status_code} while {action}: {response.text[:200]}"
            )
        try:
            return response.json()
        except ValueError as exc:
            snippet = response.text[:200] or "<empty body>"
            content_type = response.headers.get("content-type", "unknown")
            raise RttError(
                "RealTimeTrains returned a non-JSON response while "
                f"{action} (status {response.status_code}, content-type {content_type}): {snippet}"
            ) from exc

    @staticmethod
    def _select_destination(detail: dict[str, Any]) -> tuple[str, str]:
        destinations = detail.get("destination") or []
        if destinations:
            dest = destinations[0]
            return dest.get("description", "Unknown"), dest.get("crs", "")
        return "Unknown", ""

    @staticmethod
    def _parse_calling_points(detail: dict[str, Any]) -> Sequence[CallingPoint]:
        call_points = detail.get("callPoints") or []
        parsed: list[CallingPoint] = []
        for point in call_points:
            location = point.get("location") or {}
            parsed.append(
                CallingPoint(
                    station_name=location.get("description", ""),
                    station_code=location.get("crs", ""),
                    aimed_arrival_time=point.get("gbttBookedArrival") or point.get("gbttBookedPass"),
                    expected_arrival_time=point.get("realtimeArrival") or point.get("realtimePass"),
                )
            )
        return parsed

    @staticmethod
    def _derive_status(detail: dict[str, Any]) -> str:
        if detail.get("isCancelled"):
            return "CANCELLED"
        display = detail.get("displayAs")
        if display:
            return display.upper()
        realtime_actual = detail.get("realtimeDepartureActual")
        if realtime_actual:
            return f"DEPARTED {realtime_actual}"
        realtime = detail.get("realtimeDeparture")
        if realtime:
            return f"EXPECTED {realtime}"
        return "UNKNOWN"


def create_rtt_client(settings: RttSettings) -> RttClient:
    """Factory helper to create an RTT client."""

    return RttClient(settings)
