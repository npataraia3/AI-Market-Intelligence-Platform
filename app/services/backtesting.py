from __future__ import annotations

import numpy as np
import pandas as pd
from xgboost import XGBRegressor

ANNUALIZATION = 365
TEST_FRACTION = 0.4
WARMUP_DAYS = 40
COST_PER_TRADE = 0.002  # 0.1% fee + 0.1% slippage per trade
FEATURES = ["lag_1", "lag_2", "lag_7", "return_1", "return_7", "sma_7", "sma_30", "rsi_14", "volatility_14", "volume_usd", "vwap", "fear_greed"]


def _available_columns(frame: pd.DataFrame) -> list[str]:
    return [column for column in FEATURES if column in frame.columns]


def _strategy_positions(frame: pd.DataFrame, start: int, feature_columns: list[str]) -> dict[str, pd.Series]:
    """Position (0/1) series over the test window for each technical strategy."""
    positions: dict[str, pd.Series] = {}
    test = frame.iloc[start:]
    price = test["price_usd"]

    positions["Buy & Hold"] = pd.Series(1.0, index=price.index)

    if {"sma_7", "sma_30"}.issubset(frame.columns):
        positions["SMA crossover"] = (frame["sma_7"] > frame["sma_30"]).astype(float).loc[price.index]

    if "rsi_14" in frame.columns:
        raw = frame["rsi_14"]
        state = np.where(raw < 30, 1.0, np.where(raw > 70, 0.0, np.nan))
        state = pd.Series(state, index=raw.index).ffill().fillna(1.0)
        positions["RSI mean-reversion"] = state.loc[price.index]

    if {"bollinger_upper", "bollinger_lower"}.issubset(frame.columns):
        raw = np.where(
            frame["price_usd"] < frame["bollinger_lower"], 1.0,
            np.where(frame["price_usd"] > frame["bollinger_upper"], 0.0, np.nan),
        )
        state = pd.Series(raw, index=frame.index).ffill().fillna(1.0)
        positions["Bollinger mean-reversion"] = state.loc[price.index]

    if len(frame) > 20:
        momentum = (price / frame["price_usd"].shift(20).loc[price.index] - 1)
        positions["20-day Momentum"] = (momentum > 0).astype(float)
    else:
        positions["20-day Momentum"] = pd.Series(1.0, index=price.index)

    return positions


def _model_positions(frame: pd.DataFrame, start: int, feature_columns: list[str]) -> tuple[pd.Series, str]:
    """Walk-forward direction strategy: XGBoost fitted on returns from the
    training window only (no leakage), then traded on the test window."""
    fallback = pd.Series(1.0, index=frame.iloc[start:].index), "Buy & Hold"
    train = frame.iloc[:start].dropna(subset=feature_columns + ["next_return"])
    if len(train) < 40:
        return fallback
    model = XGBRegressor(n_estimators=120, max_depth=3, learning_rate=0.05, subsample=0.9, objective="reg:squarederror", random_state=42, n_jobs=1)
    model.fit(train[feature_columns], train["next_return"])
    test = frame.iloc[start:]
    X = test[feature_columns].fillna(0)
    predictions = pd.Series(model.predict(X), index=test.index)
    return (predictions > 0).astype(float), "XGBoost signal"


def _evaluate(positions: pd.Series, returns: pd.Series, label: str) -> dict:
    """Compute strategy performance including transaction costs and slippage."""
    asset_returns = returns.loc[positions.index]
    previous = positions.shift(1).fillna(positions.iloc[0])
    trades = (previous != positions).sum()
    strategy_returns = asset_returns * previous.to_numpy() - COST_PER_TRADE * (previous != positions).astype(float)
    equity = (1 + strategy_returns).cumprod()
    total_return = float(equity.iloc[-1] - 1)

    if len(equity) > 1:
        daily = strategy_returns
        annualized_return = float((1 + total_return) ** (ANNUALIZATION / len(equity)) - 1) if total_return > -1 else -1.0
        sharpe = float(annualized_return / (daily.std() * np.sqrt(ANNUALIZATION))) if daily.std() > 0 else 0.0
        peak = equity.cummax()
        max_drawdown = float((equity / peak - 1).min())
    else:
        annualized_return, sharpe, max_drawdown = 0.0, 0.0, 0.0

    market_days = asset_returns != 0
    win_rate = float((strategy_returns[market_days] > 0).mean()) if market_days.any() else 0.0

    return {
        "strategy": label,
        "total_return_percent": round(total_return * 100, 2),
        "annualized_return_percent": round(annualized_return * 100, 2),
        "sharpe": round(sharpe, 3),
        "max_drawdown_percent": round(max_drawdown * 100, 2),
        "win_rate_percent": round(win_rate * 100, 1),
        "num_trades": int(trades),
        "cost_per_trade_percent": COST_PER_TRADE * 100,
    }


def backtest_strategies(frame: pd.DataFrame) -> dict:
    """Run the strategy suite on the recent test window and return comparison
    results plus equity curves. Every strategy pays the same transaction costs
    and slippage, so the comparison is apples-to-apples."""
    if len(frame) < 70:
        raise ValueError("Not enough history for a meaningful backtest (need at least 70 days).")
    returns = frame["price_usd"].pct_change().dropna()
    start = max(WARMUP_DAYS, int(len(frame) * (1 - TEST_FRACTION)))
    start = min(start, len(frame) - 10)

    feature_columns = _available_columns(frame)
    positions = _strategy_positions(frame, start, feature_columns)
    model_positions, model_name = _model_positions(frame, start, feature_columns)
    positions[model_name] = model_positions

    results = []
    equity_series: dict[str, list[dict]] = {}
    timestamps = frame["timestamp"] if "timestamp" in frame.columns else pd.Series(
        frame.index.astype(str), index=frame.index
    )
    for label, position in positions.items():
        stats = _evaluate(position, returns, label)
        results.append(stats)
        previous = position.shift(1).fillna(position.iloc[0])
        equity = (1 + returns.loc[position.index] * previous.to_numpy() - COST_PER_TRADE * (previous != position).astype(float)).cumprod()
        equity_series[label] = [
            {"timestamp": str(ts), "equity": round(float(value), 5)}
            for ts, value in zip(timestamps.iloc[position.index], equity)
        ]

    results.sort(key=lambda row: row["sharpe"], reverse=True)
    return {
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "test_start": str(timestamps.iloc[start]),
        "test_end": str(timestamps.iloc[-1]),
        "test_days": len(frame) - start,
        "cost_per_trade_percent": COST_PER_TRADE * 100,
        "results": results,
        "equity_curves": equity_series,
    }
