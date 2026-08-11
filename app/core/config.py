from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_path: Path = Path(os.getenv("DATABASE_PATH", "data/market_intelligence.db"))
    tracked_coins: tuple[str, ...] = tuple(
        coin.strip() for coin in os.getenv(
            "TRACKED_COINS", "bitcoin,ethereum,solana,binancecoin,dogecoin"
        ).split(",") if coin.strip()
    )
    alert_threshold_percent: float = float(os.getenv("ALERT_THRESHOLD_PERCENT", "5"))
    coingecko_demo_api_key: str | None = os.getenv("COINGECKO_DEMO_API_KEY") or None


settings = Settings()
