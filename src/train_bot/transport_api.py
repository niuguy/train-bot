from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any, Optional, Sequence

import httpx

from .config import TransportApiSettings


class TransportApiError(RuntimeError):
    """Raised when TransportAPI returns an error response."""


@dataclass(frozen=True)
class CallingPoint:
    station_name: str
    station_code: str
    aimed_arrival_time: Optional[str]
    expected_arrival_time: Optional[str]


@dataclass(frozen=True)
class Departure:
    service: str
    destination_name: str
    destination_code: str
    platform: Optional[str]
    aimed_departure_time: str
    expected_departure_time: str
    status: str
    calling_points: Sequence[CallingPoint]
    operator_name: Optional[str]
    train_uid: Optional[str]


@dataclass(frozen=True)
class StationSummary:
    name: str
    station_code: str


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
        """Return upcoming departures from origin, optionally filtered by destination."""

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
        if response.status_code >= 400:
            raise TransportApiError(
                f"TransportAPI error {response.status_code}: {response.text}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            snippet = response.text[:200] or "<empty body>"
            content_type = response.headers.get("content-type", "unknown")
            raise TransportApiError(
                "TransportAPI returned a non-JSON response when requesting departures "
                f"(status {response.status_code}, content-type {content_type}): {snippet}"
            ) from exc
        try:
            departures = payload["departures"]["all"]
        except KeyError as exc:
            raise TransportApiError(
                "Unexpected TransportAPI payload structure; 'departures.all' missing"
            ) from exc

        return [self._parse_departure(item) for item in departures]

    async def search_station(self, query: str, *, limit: int = 5) -> Sequence[StationSummary]:
        """Return best matching stations for a user provided query."""

        params = {
            "app_id": self._settings.app_id,
            "app_key": self._settings.app_key,
            "query": query,
            "type": "train_station",
            "limit": str(limit),
        }

        response = await self._client.get("/uk/places.json", params=params)
        if response.status_code >= 400:
            raise TransportApiError(
                f"TransportAPI error {response.status_code}: {response.text}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            snippet = response.text[:200] or "<empty body>"
            content_type = response.headers.get("content-type", "unknown")
            raise TransportApiError(
                "TransportAPI returned a non-JSON response when searching for stations "
                f"(status {response.status_code}, content-type {content_type}): {snippet}"
            ) from exc
        members = payload.get("member", [])
        return [
            StationSummary(name=item.get("name", ""), station_code=item.get("station_code", ""))
            for item in members
            if item.get("station_code")
        ]

    @staticmethod
    def _parse_departure(data: dict[str, Any]) -> Departure:
        station_details = data.get("station_detail") or {}
        calling_points_data = station_details.get("calling_at") or data.get("calling_at") or []
        calling_points = [
            CallingPoint(
                station_name=point.get("station_name", ""),
                station_code=point.get("station_code", ""),
                aimed_arrival_time=point.get("aimed_arrival_time"),
                expected_arrival_time=point.get("expected_arrival_time"),
            )
            for point in calling_points_data
        ]

        destination = data.get("destination_name", "Unknown")
        if isinstance(destination, list):
            # Some responses provide list of destinations; take the first.
            destination_name = destination[0]
        else:
            destination_name = destination

        destination_code = ""
        for point in calling_points:
            if point.station_name == destination_name:
                destination_code = point.station_code
                break

        return Departure(
            service=data.get("service", ""),
            destination_name=destination_name,
            destination_code=destination_code,
            platform=data.get("platform"),
            aimed_departure_time=data.get("aimed_departure_time", ""),
            expected_departure_time=data.get("expected_departure_time", ""),
            status=data.get("status", ""),
            calling_points=calling_points,
            operator_name=data.get("operator_name"),
            train_uid=data.get("train_uid"),
        )


async def create_transport_client(settings: TransportApiSettings) -> TransportApiClient:
    """Factory helper to encapsulate async client creation."""

    return TransportApiClient(settings)
