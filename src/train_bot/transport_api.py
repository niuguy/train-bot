from __future__ import annotations

import datetime as dt
from typing import Any, Optional, Sequence

import httpx

from .config import TransportApiSettings
from .models import CallingPoint, Departure, StationSummary


class TransportApiError(RuntimeError):
    """Raised when TransportAPI returns an error response."""


class TransportApiClient:
    """Client for TransportAPI live departures endpoint."""

    def __init__(self, settings: TransportApiSettings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.base_url,
            timeout=10.0,
            headers={"Accept": "application/json"},
            follow_redirects=True,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "TransportApiClient":  # pragma: no cover - convenience
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - convenience
        await self.close()

    async def get_departures(
        self,
        origin_crs: str,
        *,
        destination_crs: Optional[str] = None,
        limit: int = 5,
        when: Optional[dt.datetime] = None,
    ) -> Sequence[Departure]:
        params = {
            "app_id": self._settings.app_id,
            "app_key": self._settings.app_key,
            "limit": str(limit),
            "station_detail": "calling_at",
        }
        if destination_crs:
            params["calling_at"] = destination_crs
        if when:
            params["date"] = when.strftime("%Y-%m-%d")
            params["time"] = when.strftime("%H:%M")

        path = f"/uk/train/station/{origin_crs}/live.json"
        response = await self._client.get(path, params=params)
        payload = await self._json_or_error(response, "requesting departures")

        departures = payload.get("departures", {}).get("all", [])
        return [self._parse_departure(item) for item in departures][:limit]

    async def search_station(self, query: str, *, limit: int = 5) -> Sequence[StationSummary]:
        params = {
            "app_id": self._settings.app_id,
            "app_key": self._settings.app_key,
            "query": query,
            "type": "train_station",
            "limit": str(limit),
        }
        response = await self._client.get("/uk/places.json", params=params)
        payload = await self._json_or_error(response, "searching for stations")

        members = payload.get("member", [])
        results: list[StationSummary] = []
        for item in members:
            code = item.get("station_code")
            name = item.get("name")
            if not code or not name:
                continue
            results.append(StationSummary(name=name, station_code=code))
            if len(results) >= limit:
                break
        return results

    async def _json_or_error(self, response: httpx.Response, action: str) -> dict[str, Any]:
        if response.status_code >= 400:
            raise TransportApiError(
                f"TransportAPI error {response.status_code} while {action}: {response.text[:200]}"
            )
        try:
            return response.json()
        except ValueError as exc:
            snippet = response.text[:200] or "<empty body>"
            content_type = response.headers.get("content-type", "unknown")
            raise TransportApiError(
                "TransportAPI returned a non-JSON response while "
                f"{action} (status {response.status_code}, content-type {content_type}): {snippet}"
            ) from exc

    @staticmethod
    def _parse_departure(data: dict[str, Any]) -> Departure:
        station_details = data.get("station_detail") or {}
        calling_points_data = station_details.get("calling_at") or data.get("calling_at") or []
        calling_points = [
            CallingPoint(
                station_name=point.get("station_name", ""),
                station_code=point.get("station_code", ""),
                aimed_arrival_time=point.get("aimed_arrival_time") or point.get("aimed_pass_time"),
                expected_arrival_time=point.get("expected_arrival_time"),
            )
            for point in calling_points_data
        ]

        destination_name = TransportApiClient._extract_destination_name(data)
        destination_code = TransportApiClient._find_destination_code(destination_name, calling_points)

        return Departure(
            service_uid=data.get("train_uid", ""),
            destination_name=destination_name,
            destination_code=destination_code,
            platform=data.get("platform"),
            aimed_departure_time=data.get("aimed_departure_time"),
            expected_departure_time=data.get("expected_departure_time") or data.get("aimed_departure_time"),
            status=data.get("status", ""),
            calling_points=calling_points,
            operator_name=data.get("operator_name") or data.get("operator"),
        )

    @staticmethod
    def _extract_destination_name(data: dict[str, Any]) -> str:
        destination = data.get("destination_name")
        if isinstance(destination, list):
            return destination[0]
        return destination or "Unknown"

    @staticmethod
    def _find_destination_code(name: str, calling_points: Sequence[CallingPoint]) -> str:
        for point in calling_points:
            if point.station_name == name:
                return point.station_code
        return ""


def create_transport_client(settings: TransportApiSettings) -> TransportApiClient:
    return TransportApiClient(settings)
