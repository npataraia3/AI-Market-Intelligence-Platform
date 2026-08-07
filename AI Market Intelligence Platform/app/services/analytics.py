from __future__ import annotations

from datetime import datetime, timezone
from math import sqrt

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import TimeSeriesSplit
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.stattools import adfuller
from xgboost import XGBRegressor


FEATURE_COLUMNS = [
    "lag_1", "lag_2", "lag_7", "return_1", "return_7",
    "sma_7", "sma_30", "rsi_14", "volatility_14",
    "volume_usd", "vwap", "fear_greed",
]
# Features that are recomputed from the growing price path during recursive
# multi-step forecasts; the rest (exogenous) stay at their last observed value.
_PRICE_DERIVED = {
    "lag_1", "lag_2", "lag_7", "return_1", "return_7",
    "sma_7", "sma_30", "rsi_14", "volatility_14",
}


def _metrics(actual: pd.Series, predicted: np.ndarray) -> dict[str, float]:
    # Symmetric MAPE (SMAPE): unlike plain MAPE it does not explode when a
    # near-zero actual appears in the window (common for low-priced coins).
    denominator = (np.abs(actual) + np.abs(predicted)) / 2
    smape = np.mean(np.where(denominator == 0, 0, np.abs(predicted - actual) / denominator)) * 100
    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(sqrt(mean_squared_error(actual, predicted))),
        "mape": float(smape),
    }


def _fear_greed_frame(records: list[dict]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=["date", "fear_greed"])
    data = pd.DataFrame(records)
    data["date"] = pd.to_datetime(data["timestamp"].astype(int), unit="s", utc=True).dt.date
    data["fear_greed"] = pd.to_numeric(data["value"], errors="coerce")
    return data[["date", "fear_greed"]].drop_duplicates("date").sort_values("date")


def _build_features(history: dict, fear_greed: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    prices = pd.DataFrame(history["prices"], columns=["timestamp_ms", "price_usd"])
    volumes = pd.DataFrame(history.get("total_volumes", []), columns=["timestamp_ms", "volume_usd"])
    frame = prices.merge(volumes, on="timestamp_ms", how="left")
    frame["timestamp"] = pd.to_datetime(frame["timestamp_ms"], unit="ms", utc=True)
    frame = frame.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
    frame["date"] = frame["timestamp"].dt.date
    fear = _fear_greed_frame(fear_greed)
    frame = frame.merge(fear, on="date", how="left")
    frame["fear_greed"] = frame["fear_greed"].ffill().bfill().fillna(50)
    frame["volume_usd"] = frame["volume_usd"].ffill().bfill().fillna(0)
    frame["sma_7"] = frame["price_usd"].rolling(7, min_periods=1).mean()
    frame["sma_30"] = frame["price_usd"].rolling(30, min_periods=1).mean()
    std_20 = frame["price_usd"].rolling(20, min_periods=2).std().fillna(0)
    frame["bollinger_upper"] = frame["price_usd"].rolling(20, min_periods=1).mean() + 2 * std_20
    frame["bollinger_lower"] = frame["price_usd"].rolling(20, min_periods=1).mean() - 2 * std_20
    # Rolling 7-day VWAP. An all-time cumulative VWAP lets distant history
    # dominate the "average" price, so a rolling window tracks the recent
    # volume-weighted level far better as a model feature.
    frame["vwap"] = (frame["price_usd"] * frame["volume_usd"]).rolling(7, min_periods=1).sum() / frame["volume_usd"].rolling(7, min_periods=1).sum().replace(0, np.nan)
    frame["vwap"] = frame["vwap"].fillna(frame["price_usd"])
    for lag in (1, 2, 7):
        frame[f"lag_{lag}"] = frame["price_usd"].shift(lag)
    delta = frame["price_usd"].diff()
    gains = delta.clip(lower=0).rolling(14, min_periods=2).mean()
    losses = (-delta.clip(upper=0)).rolling(14, min_periods=2).mean()
    frame["rsi_14"] = (100 - 100 / (1 + gains / losses.replace(0, np.nan))).fillna(50).clip(0, 100)
    # Momentum and volatility features capture short-term trend and risk.
    frame["return_1"] = frame["price_usd"].pct_change().fillna(0)
    frame["return_7"] = frame["price_usd"].pct_change(7).fillna(0)
    frame["volatility_14"] = frame["return_1"].rolling(14, min_periods=2).std().fillna(0)
    frame["target_next_price"] = frame["price_usd"].shift(-1)
    frame["next_return"] = frame["target_next_price"] / frame["price_usd"] - 1
    candles = frame.groupby("date", as_index=False).agg(
        open=("price_usd", "first"), high=("price_usd", "max"), low=("price_usd", "min"),
        close=("price_usd", "last"), volume_usd=("volume_usd", "sum"),
    )
    candles["date"] = candles["date"].astype(str)
    return frame, candles


def _adf_needs_differencing(series: pd.Series, max_diff: int = 1) -> int:
    """Return the smallest d (0..max_diff) for which the series tests stationary."""
    candidate = series.dropna()
    for d in range(max_diff + 1):
        try:
            pvalue = adfuller(candidate, autolag="AIC")[1]
        except (ValueError, FloatingPointError):
            break
        if pvalue < 0.05:
            return d
        candidate = candidate.diff().dropna()
    return 1


def _select_arima_order(series: pd.Series, max_pq: int = 2) -> tuple[int, int, int]:
    """Pick (p, d, q) by AIC over a small grid. d comes from an ADF test,
    then ARMA(p, q) orders are scored on the (differenced) series."""
    d = _adf_needs_differencing(series)
    work = series.diff(d).dropna() if d else series.dropna()
    if len(work) < 20:
        return 1, d, 1
    search = work.tail(400)  # AIC on the recent sample is enough for order selection
    best_aic, best_order = np.inf, (1, d, 1)
    for p in range(max_pq + 1):
        for q in range(max_pq + 1):
            if p == 0 and q == 0:
                continue
            try:
                fit = ARIMA(search, order=(p, d, q), trend="n").fit(method_kwargs={"disp": False, "maxiter": 200})
            except (ValueError, np.linalg.LinAlgError, FloatingPointError, OverflowError):
                continue
            if np.isfinite(fit.aic) and fit.aic < best_aic:
                best_aic, best_order = fit.aic, (p, d, q)
    return best_order


def _price_derived(prices: list[float]) -> dict[str, float]:
    """Recompute price-derived features from a growing price path so recursive
    multi-step forecasts stay internally consistent (indicators track the
    predicted prices instead of freezing at the last observed value)."""
    p = np.asarray(prices, dtype=float)
    n = len(p)
    last = p[-1]
    features = {
        "lag_1": float(p[-2]) if n >= 2 else last,
        "lag_2": float(p[-3]) if n >= 3 else last,
        "lag_7": float(p[-8]) if n >= 8 else float(p[0]),
        "sma_7": float(p[-7:].mean()) if n >= 7 else float(p.mean()),
        "sma_30": float(p[-30:].mean()) if n >= 30 else float(p.mean()),
        "return_1": float(last / p[-2] - 1) if n >= 2 else 0.0,
        "return_7": float(last / p[-8] - 1) if n >= 8 else 0.0,
    }
    if n >= 15:
        returns = np.diff(p)
        gains = returns[returns > 0].mean() if (returns > 0).any() else 0.0
        losses = -returns[returns < 0].mean() if (returns < 0).any() else 0.0
        features["rsi_14"] = 100.0 if losses == 0 else float(100 - 100 / (1 + gains / losses))
        features["volatility_14"] = float(np.std(returns[-14:]))
    else:
        features["rsi_14"] = 50.0
        features["volatility_14"] = 0.0
    return features


def _recursive_predict(model, last_row: pd.Series, recent_prices: list[float], steps: int) -> list[float]:
    """Run a fitted return-predicting ML model step-by-step.

    The model is trained on next-day *returns* (bounded, close to stationary),
    so the price path is rebuilt by compounding ``price * (1 + return)``. This
    avoids the instability of recursive price-level prediction, where a linear
    model can diverge to astronomical values (seen in practice: -1.6e94)."""
    exogenous = {column: last_row[column] for column in FEATURE_COLUMNS if column not in _PRICE_DERIVED}
    window = recent_prices[-30:]
    predictions: list[float] = []
    for _ in range(steps):
        row = dict(exogenous)
        row.update(_price_derived(window))
        frame_row = pd.DataFrame([[row[column] for column in FEATURE_COLUMNS]], columns=FEATURE_COLUMNS)
        ret = float(model.predict(frame_row)[0])
        if not np.isfinite(ret):
            ret = 0.0
        # A single-day move beyond +/-25% is not a credible daily forecast;
        # clamping also guarantees the compounding path can never diverge.
        ret = min(max(ret, -0.25), 0.25)
        price = window[-1] * (1 + ret)
        predictions.append(price)
        window.append(price)
        window.pop(0)
    return predictions


def _rolling_evaluation(frame: pd.DataFrame, arima_order: tuple[int, int, int]) -> tuple[list[dict], pd.DataFrame]:
    train = frame.dropna(subset=FEATURE_COLUMNS + ["target_next_price", "next_return"]).copy()
    if len(train) < 50:
        return [], pd.DataFrame(columns=["timestamp", "actual_return", "signal", "strategy_return"])
    folds = min(5, max(2, len(train) // 30))
    splitter = TimeSeriesSplit(n_splits=folds)
    arima_label = f"ARIMA({arima_order[0]},{arima_order[1]},{arima_order[2]})"
    results: dict[str, list[tuple[float, float, str]]] = {
        "Linear Regression": [], "XGBoost Regressor": [], arima_label: [], "Persistence (naive)": [],
    }
    signal_rows: list[dict] = []
    for train_index, test_index in splitter.split(train):
        train_part, test_part = train.iloc[train_index], train.iloc[test_index]
        # ML models predict next-day returns, then we reconstruct prices so the
        # comparison stays in the same USD space as ARIMA and the naive baseline.
        linear = LinearRegression().fit(train_part[FEATURE_COLUMNS], train_part["next_return"])
        xgb = XGBRegressor(n_estimators=120, max_depth=3, learning_rate=0.05, subsample=0.9, objective="reg:squarederror", random_state=42, n_jobs=1)
        xgb.fit(train_part[FEATURE_COLUMNS], train_part["next_return"])
        price_level = test_part["price_usd"].to_numpy()
        predictions = {
            "Linear Regression": price_level * (1 + linear.predict(test_part[FEATURE_COLUMNS])),
            "XGBoost Regressor": price_level * (1 + xgb.predict(test_part[FEATURE_COLUMNS])),
            "Persistence (naive)": np.repeat(train_part["price_usd"].iloc[-1], len(test_part)),
        }
        try:
            arima_prediction = ARIMA(train_part["price_usd"], order=arima_order, trend="n").fit(method_kwargs={"disp": False, "maxiter": 200}).forecast(steps=len(test_part))
            predictions[arima_label] = np.asarray(arima_prediction)
        except (ValueError, np.linalg.LinAlgError, FloatingPointError):
            predictions[arima_label] = np.repeat(train_part["price_usd"].iloc[-1], len(test_part))
        for model_name, prediction in predictions.items():
            actual = test_part["target_next_price"]
            score = _metrics(actual, prediction)
            results[model_name].append((score["mae"], score["rmse"], str(test_part["timestamp"].iloc[-1])))
            if model_name == "XGBoost Regressor":
                for _, row in test_part.assign(predicted=prediction).iterrows():
                    signal_rows.append({
                        "timestamp": row["timestamp"], "actual_return": row["next_return"],
                        "signal": "BUY" if row["predicted"] > row["price_usd"] * 1.003 else "HOLD",
                        "strategy_return": row["next_return"] if row["predicted"] > row["price_usd"] * 1.003 else 0.0,
                    })
    comparison = []
    for model_name, values in results.items():
        mae_values, rmse_values, _ = zip(*values)
        comparison.append({"model": model_name, "mae": round(float(np.mean(mae_values)), 4), "rmse": round(float(np.mean(rmse_values)), 4), "folds": len(values)})
    return sorted(comparison, key=lambda row: row["rmse"]), pd.DataFrame(signal_rows)


LONG_HORIZON_STEPS = 90


def _feature_importance(frame: pd.DataFrame) -> list[dict]:
    """Gain-based feature importance from a full-data XGBoost fit for interpretability."""
    train = frame.dropna(subset=FEATURE_COLUMNS + ["next_return"])
    if len(train) < 20:
        return []
    model = XGBRegressor(n_estimators=160, max_depth=3, learning_rate=0.05, subsample=0.9, objective="reg:squarederror", random_state=42, n_jobs=1)
    model.fit(train[FEATURE_COLUMNS], train["next_return"])
    importance = sorted(zip(FEATURE_COLUMNS, model.feature_importances_), key=lambda pair: pair[1], reverse=True)
    return [{"feature": feature, "importance": round(float(value), 4)} for feature, value in importance]


def _ml_model(selected_model: str):
    if selected_model == "Linear Regression":
        return LinearRegression()
    return XGBRegressor(n_estimators=160, max_depth=3, learning_rate=0.05, subsample=0.9, objective="reg:squarederror", random_state=42, n_jobs=1)


def _forecast(frame: pd.DataFrame, selected_model: str, steps: int = 7, arima_order: tuple[int, int, int] = (1, 1, 1)) -> tuple[list[dict], float, str]:
    train = frame.dropna(subset=FEATURE_COLUMNS + ["target_next_price", "next_return"]).copy()
    use_arima = steps > LONG_HORIZON_STEPS or selected_model.startswith("ARIMA(")
    arima_label = f"ARIMA({arima_order[0]},{arima_order[1]},{arima_order[2]})"
    method = arima_label if use_arima else selected_model
    model = _ml_model(selected_model)
    if use_arima:
        try:
            # ARIMA is used for long horizons because multi-step ARIMA
            # forecasts are designed for direct h-step prediction, whereas
            # recursive tree/linear forecasts compound their own errors.
            fitted = ARIMA(frame["price_usd"], order=arima_order, trend="n").fit(method_kwargs={"disp": False, "maxiter": 200})
            predictions = np.asarray(fitted.forecast(steps=steps))
            residual_std = float(np.std(fitted.resid))
        except (ValueError, np.linalg.LinAlgError, FloatingPointError, OverflowError):
            method = selected_model
            model.fit(train[FEATURE_COLUMNS], train["next_return"])
            predictions = _recursive_predict(model, frame.iloc[-1], frame["price_usd"].tolist(), steps)
            in_sample = train["price_usd"].to_numpy() * (1 + model.predict(train[FEATURE_COLUMNS]))
            residual_std = float(np.std(in_sample - train["target_next_price"].to_numpy()))
    else:
        model.fit(train[FEATURE_COLUMNS], train["next_return"])
        predictions = _recursive_predict(model, frame.iloc[-1], frame["price_usd"].tolist(), steps)
        in_sample = train["price_usd"].to_numpy() * (1 + model.predict(train[FEATURE_COLUMNS]))
        residual_std = float(np.std(in_sample - train["target_next_price"].to_numpy()))
    # The prediction interval widens with sqrt(horizon), reflecting that
    # uncertainty accumulates the further into the future we forecast.
    growth = np.sqrt(np.arange(1, steps + 1))
    timestamp = frame["timestamp"].iloc[-1]
    forecasts = [
        {"timestamp": (timestamp + pd.Timedelta(days=offset + 1)).isoformat(), "price_usd": round(float(value), 4),
         "lower_95": round(float(value - 1.96 * residual_std * growth[offset]), 4),
         "upper_95": round(float(value + 1.96 * residual_std * growth[offset]), 4)}
        for offset, value in enumerate(predictions)
    ]
    return forecasts, residual_std, method


def analyze_history(history: dict, fear_greed: list[dict] | None = None, forecast_days: int = 7) -> dict:
    """Return features, rigorous time-series validation, forecast and backtest data."""
    frame, candles = _build_features(history, fear_greed or [])
    arima_order = _select_arima_order(frame["price_usd"])
    comparison, signals = _rolling_evaluation(frame, arima_order)
    selected_model = comparison[0]["model"] if comparison else "Linear Regression"
    forecast, residual_std, forecast_method = _forecast(frame, selected_model, forecast_days, arima_order)
    feature_importance = _feature_importance(frame)
    current = frame.iloc[-1]
    recent = frame["price_usd"].tail(min(30, len(frame)))
    try:
        adf_pvalue = float(adfuller(frame["price_usd"].diff().dropna(), autolag="AIC")[1])
    except ValueError:
        adf_pvalue = None
    if signals.empty:
        strategy_return = hold_return = 0.0
    else:
        strategy_return = float((1 + signals["strategy_return"].fillna(0)).prod() - 1)
        hold_return = float((1 + signals["actual_return"].fillna(0)).prod() - 1)
    trend = "bullish" if current.sma_7 > current.sma_30 else "bearish"
    rsi_state = "overbought" if current.rsi_14 >= 70 else "oversold" if current.rsi_14 <= 30 else "neutral"
    band_state = "above upper band" if current.price_usd > current.bollinger_upper else "below lower band" if current.price_usd < current.bollinger_lower else "within bands"
    series_columns = ["timestamp", "price_usd", "volume_usd", "sma_7", "sma_30", "rsi_14", "vwap", "bollinger_upper", "bollinger_lower", "fear_greed"]
    series = frame[series_columns].copy()
    series["timestamp"] = series["timestamp"].astype(str)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "series": series.round(4).to_dict(orient="records"), "candles": candles.round(4).to_dict(orient="records"),
        "forecast": forecast, "model_comparison": comparison, "feature_importance": feature_importance,
        "signals": signals.assign(timestamp=lambda data: data["timestamp"].astype(str)).round(6).to_dict(orient="records"),
        "metrics": {
            "current_price": round(float(current.price_usd), 4), "sma_7": round(float(current.sma_7), 4), "sma_30": round(float(current.sma_30), 4),
            "rsi_14": round(float(current.rsi_14), 2), "rsi_state": rsi_state, "trend": trend,
            "volatility_percent": round(float(recent.pct_change().std() * 100), 3), "vwap": round(float(current.vwap), 4),
            "fear_greed": round(float(current.fear_greed), 1), "bollinger_state": band_state,
            "adf_pvalue": round(adf_pvalue, 5) if adf_pvalue is not None else None,
            "is_stationary_after_difference": adf_pvalue < 0.05 if adf_pvalue is not None else None,
            "selected_model": selected_model, "prediction_interval_std": round(residual_std, 4),
            "forecast_method": forecast_method,
            "strategy_return_percent": round(strategy_return * 100, 3), "buy_hold_return_percent": round(hold_return * 100, 3),
        },
    }
