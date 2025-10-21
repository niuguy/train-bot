from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Self


@dataclass(frozen=True)
class TransportApiSettings:
    """Settings required to authenticate with TransportAPI."""

    app_id: str
    app_key: str
    base_url: str = "https://transportapi.com/v3"

    @classmethod
    def from_env(cls) -> Self:
        """Read credentials from environment variables."""

        try:
            app_id = os.environ["TRANSPORT_API_APP_ID"]
            app_key = os.environ["TRANSPORT_API_APP_KEY"]
        except KeyError as exc:  # pragma: no cover - trivial
            missing = exc.args[0]
            raise RuntimeError(
                f"Missing TransportAPI credential in environment: {missing}"
            ) from None

        base_url = os.environ.get("TRANSPORT_API_BASE_URL", cls.base_url)
        return cls(app_id=app_id, app_key=app_key, base_url=base_url)


@dataclass(frozen=True)
class BotSettings:
    """Configuration options for the Telegram bot."""

    telegram_token: str
    transport_api: TransportApiSettings
    default_station_filter_limit: int = 5

    @classmethod
    def from_env(cls) -> Self:
        """Create settings object from environment variables."""

        try:
            telegram_token = os.environ["TELEGRAM_BOT_TOKEN"]
        except KeyError as exc:  # pragma: no cover - trivial
            missing = exc.args[0]
            raise RuntimeError(
                f"Missing Telegram credential in environment: {missing}"
            ) from None

        transport_api = TransportApiSettings.from_env()
        limit = int(os.environ.get("DEFAULT_RESULT_LIMIT", 5))
        return cls(
            telegram_token=telegram_token,
            transport_api=transport_api,
            default_station_filter_limit=limit,
        )
