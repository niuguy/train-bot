from __future__ import annotations

from telegram.ext import Application, ApplicationBuilder, CommandHandler

from .commands import help_command, journey, start, stations
from .config import BotSettings
from .transport_api import TransportApiClient


def build_application(settings: BotSettings) -> Application:
    """Configure the Telegram application with command handlers."""

    transport_client = TransportApiClient(settings.transport_api)

    async def _close_client(application: Application) -> None:  # pragma: no cover - lifecycle
        await transport_client.close()

    application = (
        ApplicationBuilder()
        .token(settings.telegram_token)
        .post_shutdown(_close_client)
        .build()
    )

    application.bot_data["settings"] = settings
    application.bot_data["transport_client"] = transport_client

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stations", stations))
    application.add_handler(CommandHandler("journey", journey))

    return application
