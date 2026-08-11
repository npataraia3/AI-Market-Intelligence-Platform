from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

ANNUALIZATION = 365
CONFIDENCE = 0.95


def _returns(prices: pd.Series) -> pd.Series:
    return prices.pct_change().dropna()


def _annualized(period_return_std: float) -> float:
    return float(period_return_std * np.sqrt(ANNUALIZATION))


def risk_analytics(frame: pd.DataFrame) -> dict:
    """Risk metrics for the asset: volatility, drawdown, VaR/CVaR and ratios.

    All risk measures are computed from the observed price history (no model
    assumptions beyond the parametric VaR, which assumes a normal distribution
    and is reported alongside the fully non-parametric historical VaR).
    """
    prices = frame["price_usd"]
    returns = _returns(prices)
    if returns.empty:
        raise ValueError("Not enough price history to compute risk metrics.")

    mean_return = float(returns.mean())
    daily_std = float(returns.std())

    rolling_vol = {}
    for label, window in (("7d", 7), ("30d", 30)):
        value = returns.rolling(window, min_periods=max(5, window // 2)).std().iloc[-1]
        rolling_vol[label] = float(value * np.sqrt(ANNUALIZATION) * 100) if np.isfinite(value) else None

    annualized_vol = _annualized(daily_std) * 100

    # Maximum drawdown over the full window.
    cumulative = (1 + returns).cumprod()
    running_peak = cumulative.cummax()
    drawdown = cumulative / running_peak - 1
    max_drawdown = float(drawdown.min())

    # Historical (non-parametric) VaR and CVaR / Expected Shortfall.
    historical_var = float(np.percentile(returns, (1 - CONFIDENCE) * 100))
    cvar = float(returns[returns <= np.percentile(returns, (1 - CONFIDENCE) * 100)].mean())

    # Parametric VaR under normality (z * sigma for a zero-mean assumption).
    z_score = scipy_stats.norm.ppf(1 - CONFIDENCE)
    parametric_var = float(z_score * daily_std)

    # Annualized performance ratios (0% risk-free rate).
    annualized_return = float((1 + mean_return) ** ANNUALIZATION - 1)
    sharpe = float(annualized_return / _annualized(daily_std)) if daily_std > 0 else 0.0

    downside = returns[returns < 0].std() if (returns < 0).any() else 0.0
    sortino = float(annualized_return / (downside * np.sqrt(ANNUALIZATION))) if downside > 0 else 0.0
    calmar = float(annualized_return / abs(max_drawdown)) if max_drawdown < 0 else 0.0

    # 30-day value-at-risk for practical interpretation.
    value_30 = float(prices.iloc[-1]) * abs(historical_var)
    drawdown_series = [
        {"timestamp": str(timestamp), "drawdown": round(float(value), 4)}
        for timestamp, value in zip(drawdown.index, drawdown)
    ]

    return {
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "current_price": round(float(prices.iloc[-1]), 4),
        "volatility_percent": {
            "daily": round(daily_std * 100, 3),
            "7d": round(rolling_vol["7d"], 3) if rolling_vol["7d"] is not None else None,
            "30d": round(rolling_vol["30d"], 3) if rolling_vol["30d"] is not None else None,
            "annualized": round(annualized_vol, 3),
        },
        "max_drawdown_percent": round(max_drawdown * 100, 3),
        "var": {
            "confidence": CONFIDENCE,
            "historical_var_percent": round(historical_var * 100, 3),
            "parametric_var_percent": round(parametric_var * 100, 3),
            "cvar_percent": round(cvar * 100, 3),
            "value_at_risk_1d_usd": round(value_30, 2),
            "interpretation": (
                f"At {int(CONFIDENCE * 100)}% confidence, the estimated one-day loss "
                f"is no worse than ~${value_30:,.0f} under the historical distribution."
            ),
        },
        "ratios": {
            "sharpe": round(sharpe, 3),
            "sortino": round(sortino, 3),
            "calmar": round(calmar, 3),
            "annualized_return_percent": round(annualized_return * 100, 3),
        },
        "drawdown_series": drawdown_series,
    }
