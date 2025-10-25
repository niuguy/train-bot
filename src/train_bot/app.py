from __future__ import annotations

from telegram.ext import Application, ApplicationBuilder, CommandHandler

from .commands import help_command, journey, start, stations
from .config import BotSettings
from .providers import RailProvider
from .rtt_api import RttClient
from .transport_api import TransportApiClient


def build_application(settings: BotSettings) -> Application:
    """Configure the Telegram application with command handlers."""

    providers: list[RailProvider] = []
    clients_to_close = []

    if settings.rtt_settings:
        rtt_client = RttClient(settings.rtt_settings)
        providers.append(RailProvider(name="RealTimeTrains", client=rtt_client))
        clients_to_close.append(rtt_client)

    if settings.transport_settings:
        transport_client = TransportApiClient(settings.transport_settings)
        providers.append(RailProvider(name="TransportAPI", client=transport_client))
        clients_to_close.append(transport_client)

    async def _close_client(application: Application) -> None:  # pragma: no cover - lifecycle
        for client in clients_to_close:
            await client.close()

    application = (
        ApplicationBuilder()
        .token(settings.telegram_token)
        .post_shutdown(_close_client)
        .build()
    )

    application.bot_data["settings"] = settings
    application.bot_data["rail_providers"] = providers

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stations", stations))
    application.add_handler(CommandHandler("journey", journey))

    return application
