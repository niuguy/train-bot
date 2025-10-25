from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List, Sequence

import httpx

from .models import Departure, StationSummary
from .transport_api import TransportApiError
from .rtt_api import RttError

ProviderError = (RttError, TransportApiError)


@dataclass(frozen=True)
class RailProvider:
    name: str
    client: Any

    async def search_station(self, query: str, *, limit: int = 5) -> Sequence[StationSummary]:
        return await self.client.search_station(query, limit=limit)

    async def get_departures(
        self,
        origin_crs: str,
        *,
        destination_crs: str | None = None,
        limit: int = 5,
        when=None,
    ) -> Sequence[Departure]:
        return await self.client.get_departures(
            origin_crs,
            destination_crs=destination_crs,
            limit=limit,
            when=when,
        )


class AllProvidersFailed(RuntimeError):
    def __init__(self, messages: Sequence[str]) -> None:
        self.messages = list(messages)
        super().__init__("; ".join(messages))


async def call_with_fallback(
    providers: Iterable[RailProvider],
    method: str,
    *args,
    retry_on_empty: bool = False,
    **kwargs,
):
    errors: List[str] = []
    last_result = None
    last_provider = None

    for provider in providers:
        try:
            func = getattr(provider, method)
            result = await func(*args, **kwargs)
        except ProviderError as exc:
            errors.append(f"{provider.name}: {exc}")
            continue
        except httpx.HTTPError as exc:
            errors.append(f"{provider.name}: network error {exc}")
            continue

        if result or not retry_on_empty:
            return result, provider.name, errors

        last_result = result
        last_provider = provider.name

    if last_result is not None and last_provider is not None:
        return last_result, last_provider, errors

    if errors:
        raise AllProvidersFailed(errors)

    return [], None, errors
