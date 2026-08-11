from __future__ import annotations

import numpy as np
import pandas as pd

ANNUALIZATION = 365


def _price_series(frame: pd.DataFrame) -> pd.Series:
    return frame["price_usd"].astype(float)


def _align_returns(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    returns = pd.DataFrame({
        coin_id: frame["price_usd"].pct_change()
        for coin_id, frame in frames.items()
    }).dropna()
    return returns


def compare_assets(frames: dict[str, pd.DataFrame]) -> dict:
    """Cross-asset market structure: performance, risk, correlation and the
    rolling charts needed for the overview page."""
    if not frames:
        raise ValueError("No assets provided for comparison.")

    returns = _align_returns(frames)
    if len(returns) < 3:
        raise ValueError("Not enough aligned history for a cross-asset comparison.")

    coins: list[dict] = []
    for coin_id, frame in frames.items():
        prices = _price_series(frame)
        r = prices.pct_change().dropna()
        current = float(prices.iloc[-1])
        perf = {
            "24h": float(prices.iloc[-1] / prices.iloc[-2] - 1) if len(prices) >= 2 else None,
            "7d": float(prices.iloc[-1] / prices.iloc[-8] - 1) if len(prices) >= 8 else None,
            "30d": float(prices.iloc[-1] / prices.iloc[-31] - 1) if len(prices) >= 31 else None,
        }
        annualized_vol = float(r.std() * np.sqrt(ANNUALIZATION)) if len(r) >= 2 else None
        cumulative = (1 + r).cumprod()
        max_drawdown = float((cumulative / cumulative.cummax() - 1).min())
        rsi = float(frame["rsi_14"].iloc[-1]) if "rsi_14" in frame.columns else None
        momentum_20 = float(prices.iloc[-1] / prices.iloc[-21] - 1) if len(prices) >= 21 else None
        sharpe = float((1 + (1 + r.mean()) ** ANNUALIZATION - 1) / (r.std() * np.sqrt(ANNUALIZATION))) if len(r) >= 2 and r.std() > 0 else None
        coins.append({
            "coin_id": coin_id,
            "price_usd": round(current, 4),
            "performance_percent": {key: (round(value * 100, 2) if value is not None else None) for key, value in perf.items()},
            "volatility_annualized_percent": round(annualized_vol * 100, 2) if annualized_vol is not None else None,
            "max_drawdown_percent": round(max_drawdown * 100, 2),
            "rsi_14": round(rsi, 1) if rsi is not None else None,
            "momentum_20d_percent": round(momentum_20 * 100, 2) if momentum_20 is not None else None,
            "sharpe": round(sharpe, 3) if sharpe is not None else None,
        })

    correlation_matrix = returns.corr().round(4).to_dict()

    # Rolling 30-day correlation for each pair against the first asset.
    pairs = list(returns.columns)
    first = pairs[0]
    rolling_corr = []
    if len(pairs) >= 2:
        rolling = returns[first].rolling(30, min_periods=15).corr(returns[pairs[1]])
        rolling_corr = [
            {"timestamp": str(ts), "pair": f"{first}-{pairs[1]}", "correlation": round(float(value), 3)}
            for ts, value in rolling.dropna().items()
        ]

    # Chart series: normalized performance and rolling volatility.
    def _timestamps(frame: pd.DataFrame) -> pd.Series:
        if "timestamp" in frame.columns:
            return pd.to_datetime(frame["timestamp"]).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        return pd.Series([str(index) for index in frame.index], index=frame.index)

    normalized = {
        coin_id: [{"timestamp": str(ts), "value": round(float(value), 4)}
                  for ts, value in zip(_timestamps(frame), frame["price_usd"] / frame["price_usd"].iloc[0])]
        for coin_id, frame in frames.items()
    }
    rolling_volatility = {}
    for coin_id, frame in frames.items():
        r = frame["price_usd"].pct_change()
        vol = r.rolling(30, min_periods=10).std() * np.sqrt(ANNUALIZATION)
        rolling_volatility[coin_id] = [
            {"timestamp": str(ts), "value": round(float(value) * 100, 3)}
            for ts, value in zip(_timestamps(frame).loc[vol.dropna().index], vol.dropna())
        ]

    drawdown = {}
    for coin_id, frame in frames.items():
        r = frame["price_usd"].pct_change()
        cumulative = (1 + r).cumprod()
        dd = cumulative / cumulative.cummax() - 1
        drawdown[coin_id] = [
            {"timestamp": str(ts), "value": round(float(value) * 100, 3)}
            for ts, value in zip(_timestamps(frame).loc[dd.dropna().index], dd.dropna())
        ]

    return {
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "coins": coins,
        "correlation_matrix": correlation_matrix,
        "rolling_correlation": rolling_corr,
        "series": {
            "normalized_performance": normalized,
            "rolling_volatility": rolling_volatility,
            "drawdown": drawdown,
        },
    }
