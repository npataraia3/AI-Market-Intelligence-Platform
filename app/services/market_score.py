from __future__ import annotations

import numpy as np
import pandas as pd

ANNUALIZATION = 365


def _score_component(name: str, points: float, max_points: float, value: str) -> dict:
    return {
        "name": name,
        "points": round(float(np.clip(points, -max_points, max_points)), 1),
        "max_points": float(max_points),
        "value": value,
    }


def market_score(frame: pd.DataFrame) -> dict:
    """Transparent 0-100 market intelligence score.

    Methodology (all rules, no black box):
    - Momentum  (+/-25): 7-day return mapped to [-25, +25].
    - Trend     (+/-20): price vs 30-day SMA.
    - Sentiment (+/-15): Fear & Greed index (greed is constructive).
    - Volume    (+/-10): current volume vs its 30-day average.
    - Volatility(+/-15): inverse — calmer markets score higher.
    - RSI       (+/-15): neutral zone is rewarded; extreme readings subtract
      (mean-reversion stance).

    The six components are summed and clamped to [0, 100].
    """
    prices = frame["price_usd"]
    if len(prices) < 8:
        raise ValueError("Not enough history to compute a market score.")

    current = prices.iloc[-1]
    return_7 = float(current / prices.iloc[-8] - 1) if len(prices) >= 8 else 0.0

    sma_30 = float(frame["sma_30"].iloc[-1]) if "sma_30" in frame.columns else float(prices.mean())
    trend_points = 20 * np.sign(current - sma_30) * min(1.0, abs(current / sma_30 - 1) / 0.10)

    fear_greed = float(frame["fear_greed"].iloc[-1]) if "fear_greed" in frame.columns and np.isfinite(frame["fear_greed"].iloc[-1]) else 50.0
    sentiment_points = (fear_greed - 50) / 50 * 15

    volume = frame.get("volume_usd")
    if volume is not None and volume.notna().sum() >= 8:
        avg_volume = float(volume.rolling(30, min_periods=8).mean().iloc[-1])
        current_volume = float(volume.iloc[-1])
        volume_points = (np.log1p(max(current_volume, 1.0)) - np.log1p(max(avg_volume, 1.0))) * 10
    else:
        volume_points = 0.0

    returns = prices.pct_change().dropna()
    vol_30 = float(returns.rolling(30, min_periods=8).std().iloc[-1] * np.sqrt(ANNUALIZATION))
    vol_points = 15 * max(0.0, 1 - vol_30 / 1.0)  # 100% annualized vol -> 0 points

    rsi = float(frame["rsi_14"].iloc[-1]) if "rsi_14" in frame.columns else 50.0
    if 45 <= rsi <= 60:
        rsi_points = 15.0
    elif 60 < rsi <= 70:
        rsi_points = 15 - (rsi - 60) * 1.0
    elif rsi > 70:
        rsi_points = -5 - (rsi - 70) * 0.5
    elif 30 <= rsi < 45:
        rsi_points = 15 - (45 - rsi) * 1.0
    else:
        rsi_points = -5 - (30 - rsi) * 0.5

    components = [
        _score_component("Momentum", 25 * np.tanh(return_7 / 0.10), 25, f"7d return {return_7 * 100:+.1f}%"),
        _score_component("Trend", trend_points, 20, f"price {'above' if current > sma_30 else 'below'} SMA-30"),
        _score_component("Sentiment", sentiment_points, 15, f"Fear & Greed {fear_greed:.0f}"),
        _score_component("Volume", volume_points, 10, f"volume vs 30d avg"),
        _score_component("Volatility", vol_points, 15, f"30d ann. vol {vol_30 * 100:.1f}%"),
        _score_component("RSI", rsi_points, 15, f"RSI-14 {rsi:.1f}"),
    ]

    score = float(sum(component["points"] for component in components))
    score = max(0.0, min(100.0, 50 + score))
    if score >= 70:
        label = "STRONG BULLISH"
    elif score >= 55:
        label = "BULLISH"
    elif score >= 45:
        label = "NEUTRAL"
    elif score >= 30:
        label = "BEARISH"
    else:
        label = "STRONG BEARISH"

    return {
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "score": round(score, 1),
        "label": label,
        "components": components,
        "methodology": (
            "Sum of six explainable factors centered at 50: momentum (7d return), "
            "trend (price vs SMA-30), sentiment (Fear & Greed), volume momentum, "
            "inverse volatility and RSI positioning. Clamped to [0, 100]."
        ),
    }
