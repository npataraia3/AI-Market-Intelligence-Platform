from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)
BASE_URL = "https://api.coingecko.com/api/v3/coins/markets"
HISTORY_URL = "https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
FEAR_GREED_URL = "https://api.alternative.me/fng/"

CACHE_DIR = Path("data/cache")
HISTORY_TTL_SECONDS = 4 * 60 * 60
FEAR_GREED_TTL_SECONDS = 6 * 60 * 60
RETRY_ATTEMPTS = 3


class MarketDataError(RuntimeError):
    pass


def _session() -> requests.Session:
    """Create an HTTP session that is not affected by stale machine proxies."""
    session = requests.Session()
    session.trust_env = False
    if settings.coingecko_demo_api_key:
        session.headers["x-cg-demo-api-key"] = settings.coingecko_demo_api_key
    return session


def _request_with_retry(session: requests.Session, method: str, url: str, **kwargs) -> requests.Response:
    """Perform a request, backing off on rate limits (429) and transient 5xx errors."""
    for attempt in range(RETRY_ATTEMPTS):
        response = session.request(method, url, **kwargs)
        if response.status_code not in {429} and not (500 <= response.status_code < 600):
            return response
        if attempt == RETRY_ATTEMPTS - 1:
            return response
        time.sleep(2 ** attempt + 1)
    return response  # pragma: no cover


def _cached_path(kind: str, key: str) -> Path:
    return CACHE_DIR / f"{kind}_{key}.json"


def _read_cache(path: Path, ttl: float) -> Any | None:
    try:
        if path.exists() and time.time() - path.stat().st_mtime < ttl:
            return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    return None


def _write_cache(path: Path, payload: Any) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
    except OSError:
        pass


def fetch_market_data(coin_ids: tuple[str, ...] | None = None) -> list[dict[str, Any]]:
    """Retrieve current USD market data from CoinGecko's public endpoint."""
    ids = coin_ids or settings.tracked_coins
    try:
        # Ignore a machine-wide proxy setting.  This keeps a local portfolio
        # app usable when an old/corporate proxy points to an unavailable host.
        response = _request_with_retry(
            _session(), "GET", BASE_URL,
            params={
                "vs_currency": "usd", "ids": ",".join(ids),
                "order": "market_cap_desc", "sparkline": "false",
                "price_change_percentage": "24h",
            },
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise MarketDataError(f"Unable to retrieve market data: {exc}") from exc
    if not isinstance(payload, list):
        raise MarketDataError("Unexpected response format from market-data provider.")
    return payload


def fetch_price_history(coin_id: str, days: int = 30) -> dict[str, Any]:
    """Fetch historical prices and trading volume for charting and indicators.

    Responses are cached to disk so repeated dashboard requests do not trip
    CoinGecko's public rate limits.
    """
    if days not in {1, 7, 30, 90, 365}:
        raise MarketDataError("History period must be one of: 1, 7, 30, 90, 365 days (CoinGecko's free API caps historical data at 365 days).")
    cache_path = _cached_path("market_chart", f"{coin_id}_{days}")
    cached = _read_cache(cache_path, HISTORY_TTL_SECONDS)
    if cached is not None:
        return cached
    try:
        response = _request_with_retry(
            _session(), "GET", HISTORY_URL.format(coin_id=coin_id),
            params={"vs_currency": "usd", "days": days, "interval": "hourly" if days <= 7 else "daily"},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise MarketDataError(f"Unable to retrieve historical market data: {exc}") from exc
    if not isinstance(payload, dict) or "prices" not in payload:
        raise MarketDataError("Unexpected historical-data format from market-data provider.")
    _write_cache(cache_path, payload)
    return payload


def fetch_fear_greed_history(limit: int = 365) -> list[dict[str, Any]]:
    """Fetch Crypto Fear & Greed Index values (free public endpoint)."""
    cache_path = _cached_path("fear_greed", str(limit))
    cached = _read_cache(cache_path, FEAR_GREED_TTL_SECONDS)
    if cached is not None:
        return cached
    try:
        response = _request_with_retry(
            _session(), "GET", FEAR_GREED_URL, params={"limit": limit, "format": "json"}, timeout=15,
        )
        response.raise_for_status()
        data = response.json().get("data", [])
        records = data if isinstance(data, list) else []
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Fear & Greed Index unavailable: %s", exc)
        return []
    _write_cache(cache_path, records)
    return records
