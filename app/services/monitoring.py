from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np

from app.core.config import settings
from app.data.database import save_alert
from app.services.market_regime import rule_based_regime

logger = logging.getLogger(__name__)

REGIME_STATE_FILE = Path("data/regime_state.json")
ANNUALIZATION = 365


def _read_regime_state() -> dict:
    try:
        if REGIME_STATE_FILE.exists():
            return json.loads(REGIME_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    return {}


def _write_regime_state(state: dict) -> None:
    try:
        REGIME_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        REGIME_STATE_FILE.write_text(json.dumps(state), encoding="utf-8")
    except OSError:
        pass


def create_alerts(rows: list[dict]) -> list[dict]:
    """24-hour price-change alerts from fresh market snapshots."""
    alerts: list[dict] = []
    for row in rows:
        change = float(row.get("price_change_percentage_24h") or 0)
        if abs(change) < settings.alert_threshold_percent:
            continue
        severity = "high" if abs(change) >= settings.alert_threshold_percent * 2 else "medium"
        direction = "rose" if change > 0 else "fell"
        message = f"{row['name']} {direction} {abs(change):.2f}% in the past 24 hours."
        alert = {"coin_id": row["id"], "severity": severity, "message": message, "change_24h_percent": change}
        save_alert(row["id"], severity, message, change)
        logger.warning(message)
        alerts.append(alert)
    return alerts


def _push(coin_id: str, severity: str, message: str, alert_type: str, alerts: list[dict]) -> None:
    save_alert(coin_id, severity, message, 0.0)
    alerts.append({"coin_id": coin_id, "severity": severity, "message": message, "type": alert_type})
    logger.warning(message)


def create_technical_alerts(coin_id: str, frame) -> list[dict]:
    """Technical, volatility, volume and regime-change alerts from the feature
    frame built by the analytics pipeline."""
    alerts: list[dict] = []
    if frame is None or frame.empty or len(frame) < 15:
        return alerts

    name = coin_id.upper()
    prices = frame["price_usd"]
    current_price = float(prices.iloc[-1])

    # --- RSI alert ---
    if "rsi_14" in frame.columns:
        rsi = float(frame["rsi_14"].iloc[-1])
        if rsi >= 70:
            _push(coin_id, "medium", f"{name} RSI = {rsi:.0f} — potentially overbought.", "rsi", alerts)
        elif rsi <= 30:
            _push(coin_id, "medium", f"{name} RSI = {rsi:.0f} — potentially oversold.", "rsi", alerts)

    # --- Bollinger alert ---
    if {"bollinger_upper", "bollinger_lower"}.issubset(frame.columns):
        upper = float(frame["bollinger_upper"].iloc[-1])
        lower = float(frame["bollinger_lower"].iloc[-1])
        if current_price > upper:
            _push(coin_id, "medium", f"{name} price crossed above the upper Bollinger Band (${upper:,.0f}).", "bollinger", alerts)
        elif current_price < lower:
            _push(coin_id, "medium", f"{name} price crossed below the lower Bollinger Band (${lower:,.0f}).", "bollinger", alerts)

    # --- Volume anomaly ---
    if "volume_usd" in frame.columns:
        volume = frame["volume_usd"]
        avg = float(volume.rolling(30, min_periods=10).mean().iloc[-1])
        current_volume = float(volume.iloc[-1])
        if avg > 0 and current_volume > 3 * avg:
            ratio = current_volume / avg
            _push(coin_id, "high", f"{name} volume is {ratio:.1f}x its 30-day average — unusual activity.", "volume", alerts)

    # --- Volatility spike ---
    if len(prices) >= 30:
        returns = prices.pct_change().dropna()
        rolling = returns.rolling(30, min_periods=10).std() * np.sqrt(ANNUALIZATION)
        current_vol = float(rolling.iloc[-1])
        historical = rolling.dropna()
        if not historical.empty and np.isfinite(current_vol):
            percentile = float((historical <= current_vol).mean() * 100)
            if percentile >= 95:
                _push(coin_id, "high", f"{name} volatility exceeded its historical 95th percentile ({current_vol * 100:.0f}% ann.).", "volatility", alerts)

    # --- Regime change ---
    previous = _read_regime_state()
    current = rule_based_regime(frame).get("regime", "UNKNOWN")
    if coin_id in previous and previous[coin_id] != current:
        _push(coin_id, "medium", f"{name} market regime changed: {previous[coin_id]} → {current}.", "regime", alerts)
    previous[coin_id] = current
    _write_regime_state(previous)

    return alerts
