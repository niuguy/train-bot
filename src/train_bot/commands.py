from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from typing import Sequence

from telegram import Update
from telegram.ext import ContextTypes

from .config import BotSettings
from .formatter import format_departures
from .models import StationSummary
from .providers import AllProvidersFailed, RailProvider, call_with_fallback


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

    providers = _providers(context)
    try:
        results, provider_name, errors = await call_with_fallback(
            providers, "search_station", query, limit=5, retry_on_empty=True
        )
    except AllProvidersFailed as exc:
        await update.message.reply_text(
            "All data providers failed while searching for stations:\n" + "\n".join(exc.messages)
        )
        return

    if not results:
        await update.message.reply_text("No stations found for that search term.")
        return

    lines = [f"{station.name} — {station.station_code}" for station in results]
    header = f"Station matches (via {provider_name})" if provider_name else "Station matches"
    if errors:
        header += "\n" + "\n".join(f"Fallback note: {err}" for err in errors)
    await update.message.reply_text(f"{header}:\n" + "\n".join(lines))


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
    providers = _providers(context)

    try:
        origin_candidates, origin_provider, origin_errors = await call_with_fallback(
            providers,
            "search_station",
            request.origin_query,
            limit=3,
            retry_on_empty=True,
        )
        destination_candidates, destination_provider, destination_errors = await call_with_fallback(
            providers,
            "search_station",
            request.destination_query,
            limit=3,
            retry_on_empty=True,
        )
    except AllProvidersFailed as exc:
        await update.message.reply_text(
            "All data providers failed while resolving stations:\n" + "\n".join(exc.messages)
        )
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
        departures, departure_provider, departure_errors = await call_with_fallback(
            providers,
            "get_departures",
            origin.station_code,
            destination_crs=destination.station_code,
            limit=settings.default_station_filter_limit,
            when=request.when,
            retry_on_empty=True,
        )
    except AllProvidersFailed as exc:
        await update.message.reply_text(
            "All data providers failed while fetching departures:\n" + "\n".join(exc.messages)
        )
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

    diagnostics: list[str] = []
    if origin_errors:
        diagnostics.extend(f"Origin fallback: {err}" for err in origin_errors)
    if destination_errors:
        diagnostics.extend(f"Destination fallback: {err}" for err in destination_errors)
    if departure_errors:
        diagnostics.extend(f"Departure fallback: {err}" for err in departure_errors)

    provider_note = (
        f"\n\nData source: {departure_provider or origin_provider or destination_provider}"
        if (departure_provider or origin_provider or destination_provider)
        else ""
    )

    diagnostic_note = ("\n" + "\n".join(diagnostics)) if diagnostics else ""

    await update.message.reply_text(message + suffix + provider_note + diagnostic_note)


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


def _providers(context: ContextTypes.DEFAULT_TYPE) -> Sequence[RailProvider]:
    return context.application.bot_data["rail_providers"]


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
