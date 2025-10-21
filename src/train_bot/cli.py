from __future__ import annotations

from dotenv import load_dotenv

from .app import build_application
from .config import BotSettings


def main() -> None:
    """Entry point for launching the Telegram bot."""

    load_dotenv()
    settings = BotSettings.from_env()
    application = build_application(settings)
    application.run_polling()


def run() -> None:  # pragma: no cover - compatibility alias
    main()
