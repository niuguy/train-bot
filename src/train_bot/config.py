from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Self


@dataclass(frozen=True)
class RttSettings:
    """Credentials and options for the RealTimeTrains API."""

    username: str
    password: str
    base_url: str = "https://api.rtt.io"

    @classmethod
    def from_env_optional(cls) -> Optional[Self]:
        username = os.environ.get("RTT_USERNAME")
        password = os.environ.get("RTT_PASSWORD")
        if not username or not password:
            return None

        base_url = os.environ.get("RTT_BASE_URL", cls.base_url)
        return cls(username=username, password=password, base_url=base_url)


@dataclass(frozen=True)
class TransportApiSettings:
    """Settings required to authenticate with TransportAPI."""

    app_id: str
    app_key: str
    base_url: str = "https://transportapi.com/v3"

    @classmethod
    def from_env_optional(cls) -> Optional[Self]:
        app_id = os.environ.get("TRANSPORT_API_APP_ID")
        app_key = os.environ.get("TRANSPORT_API_APP_KEY")
        if not app_id or not app_key:
            return None
        base_url = os.environ.get("TRANSPORT_API_BASE_URL", cls.base_url)
        return cls(app_id=app_id, app_key=app_key, base_url=base_url)


@dataclass(frozen=True)
class BotSettings:
    """Configuration options for the Telegram bot."""

    telegram_token: str
    rtt_settings: Optional[RttSettings]
    transport_settings: Optional[TransportApiSettings]
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

        rtt_settings = RttSettings.from_env_optional()
        transport_settings = TransportApiSettings.from_env_optional()

        if not rtt_settings and not transport_settings:
            raise RuntimeError(
                "At least one rail data provider must be configured."
            )

        limit = int(os.environ.get("DEFAULT_RESULT_LIMIT", 5))
        return cls(
            telegram_token=telegram_token,
            rtt_settings=rtt_settings,
            transport_settings=transport_settings,
            default_station_filter_limit=limit,
        )
