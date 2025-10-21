from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from typing import Sequence

import httpx
from telegram import Update
from telegram.ext import ContextTypes

from .config import BotSettings
from .formatter import format_departures
from .transport_api import (
    StationSummary,
    TransportApiClient,
    TransportApiError,
)


@dataclass(frozen=True)
class JourneyRequest:
    origin_query: str
    destination_query: str
    when: dt.datetime | None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send greeting and usage basics."""

    message = (
        "👋 Hi! Send /journey followed by origin and destination, e.g.\n"
        "/journey London Waterloo to Winchester at 17:30\n\n"
        "Need a station code? Try /stations <search term>."
    )
    await update.message.reply_text(message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = (
        "Usage:\n"
        "  /journey <origin> to <destination> [at HH:MM]\n"
        "  /stations <search term>\n\n"
        "Examples:\n"
        "  /journey Manchester Piccadilly to London Euston\n"
        "  /journey Leeds to York at 09:15\n"
        "  /stations Paddington"
    )
    await update.message.reply_text(message)


async def stations(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Look up station codes matching a free text query."""

    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("Please supply a station name, e.g. /stations York")
        return

    client = _transport_client(context)
    try:
        results = await client.search_station(query)
    except TransportApiError as exc:
        await update.message.reply_text(f"Transport API error: {exc}")
        return
    except httpx.HTTPError as exc:
        await update.message.reply_text(f"Network error talking to TransportAPI: {exc}")
        return

    if not results:
        await update.message.reply_text("No stations found for that search term.")
        return

    lines = [f"{station.name} — {station.station_code}" for station in results]
    await update.message.reply_text("Station matches:\n" + "\n".join(lines))


async def journey(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /journey command to list departures."""

    if not context.args:
        await update.message.reply_text(
            "Please provide origin and destination, e.g. /journey Bristol Temple Meads to Bath Spa"
        )
        return

    query_text = " ".join(context.args)
    try:
        request = parse_journey_query(query_text)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return

    settings = _settings(context)
    client = _transport_client(context)

    try:
        origin_candidates = await client.search_station(request.origin_query, limit=3)
        destination_candidates = await client.search_station(request.destination_query, limit=3)
    except TransportApiError as exc:
        await update.message.reply_text(f"Transport API error: {exc}")
        return
    except httpx.HTTPError as exc:
        await update.message.reply_text(f"Network error talking to TransportAPI: {exc}")
        return

    if not origin_candidates:
        await update.message.reply_text("Couldn't find a station matching the origin.")
        return
    if not destination_candidates:
        await update.message.reply_text("Couldn't find a station matching the destination.")
        return

    origin = origin_candidates[0]
    destination = destination_candidates[0]

    try:
        departures = await client.get_departures(
            origin.station_code,
            destination_crs=destination.station_code,
            limit=settings.default_station_filter_limit,
            when=request.when,
        )
    except TransportApiError as exc:
        await update.message.reply_text(f"Transport API error: {exc}")
        return
    except httpx.HTTPError as exc:
        await update.message.reply_text(f"Network error talking to TransportAPI: {exc}")
        return

    origin_name = _tidy_station_name(origin.name)
    destination_name = _tidy_station_name(destination.name)

    message = format_departures(
        origin_name,
        destination_name,
        departures,
        requested_time=request.when,
    )

    suffix = _format_alternatives(origin_candidates, destination_candidates)
    await update.message.reply_text(message + suffix)


def parse_journey_query(text: str) -> JourneyRequest:
    """Parse free text into a JourneyRequest."""

    time_match = re.search(r"(?:\bat\s+)?(\d{1,2}:\d{2})$", text)
    when: dt.datetime | None = None
    if time_match:
        time_str = time_match.group(1)
        hours, minutes = map(int, time_str.split(":"))
        now = dt.datetime.now()
        when = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
        text = text[: time_match.start()].strip()

    parts = re.split(r"\s+(?:to|->)\s+", text, maxsplit=1)
    if len(parts) != 2:
        raise ValueError("Couldn't parse journey. Use '/journey origin to destination [at HH:MM]'.")

    origin_query, destination_query = (_strip_from_keyword(part) for part in parts)

    if not origin_query or not destination_query:
        raise ValueError("Origin and destination are both required.")

    return JourneyRequest(origin_query=origin_query, destination_query=destination_query, when=when)


def _strip_from_keyword(value: str) -> str:
    return re.sub(r"^(?:from|to)\s+", "", value.strip(), flags=re.IGNORECASE)


def _tidy_station_name(name: str) -> str:
    return re.sub(r"\bRail (Station|Stn)\b", "", name).strip()


def _settings(context: ContextTypes.DEFAULT_TYPE) -> BotSettings:
    return context.application.bot_data["settings"]


def _transport_client(context: ContextTypes.DEFAULT_TYPE) -> TransportApiClient:
    return context.application.bot_data["transport_client"]


def _format_alternatives(
    origin_candidates: Sequence[StationSummary],
    destination_candidates: Sequence[StationSummary],
) -> str:
    origin_suffix = _format_station_candidates("Origin suggestions", origin_candidates)
    destination_suffix = _format_station_candidates("Destination suggestions", destination_candidates)
    additions = f"\n\n{origin_suffix}{destination_suffix}"
    return additions if additions.strip() else ""


def _format_station_candidates(label: str, candidates: Sequence[StationSummary]) -> str:
    if len(candidates) <= 1:
        return ""

    formatted = "\n".join(
        f"- {station.name} — {station.station_code}" for station in candidates[1:3]
    )
    return f"{label}:\n{formatted}\n"
