from __future__ import annotations

from datetime import datetime, timezone
from math import sqrt

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, mean_squared_error
from sklearn.model_selection import TimeSeriesSplit
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.stattools import adfuller
from xgboost import XGBRegressor


FEATURE_COLUMNS = ["lag_1", "lag_2", "lag_7", "sma_7", "sma_30", "rsi_14", "volume_usd", "vwap", "fear_greed"]


def _metrics(actual: pd.Series, predicted: np.ndarray) -> dict[str, float]:
    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(sqrt(mean_squared_error(actual, predicted))),
        "mape": float(mean_absolute_percentage_error(actual, predicted) * 100),
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
    frame["vwap"] = (frame["price_usd"] * frame["volume_usd"]).cumsum() / frame["volume_usd"].cumsum().replace(0, np.nan)
    frame["vwap"] = frame["vwap"].fillna(frame["price_usd"])
    for lag in (1, 2, 7):
        frame[f"lag_{lag}"] = frame["price_usd"].shift(lag)
    delta = frame["price_usd"].diff()
    gains = delta.clip(lower=0).rolling(14, min_periods=2).mean()
    losses = (-delta.clip(upper=0)).rolling(14, min_periods=2).mean()
    frame["rsi_14"] = (100 - 100 / (1 + gains / losses.replace(0, np.nan))).fillna(50).clip(0, 100)
    frame["target_next_price"] = frame["price_usd"].shift(-1)
    frame["next_return"] = frame["target_next_price"] / frame["price_usd"] - 1
    candles = frame.groupby("date", as_index=False).agg(
        open=("price_usd", "first"), high=("price_usd", "max"), low=("price_usd", "min"),
        close=("price_usd", "last"), volume_usd=("volume_usd", "sum"),
    )
    candles["date"] = candles["date"].astype(str)
    return frame, candles


def _rolling_evaluation(frame: pd.DataFrame) -> tuple[list[dict], pd.DataFrame]:
    train = frame.dropna(subset=FEATURE_COLUMNS + ["target_next_price"]).copy()
    if len(train) < 50:
        return [], pd.DataFrame(columns=["timestamp", "actual_return", "signal", "strategy_return"])
    folds = min(5, max(2, len(train) // 30))
    splitter = TimeSeriesSplit(n_splits=folds)
    results: dict[str, list[tuple[float, float, str]]] = {
        "Linear Regression": [], "XGBoost Regressor": [], "ARIMA(1,1,1)": [], "Persistence (naive)": [],
    }
    signal_rows: list[dict] = []
    for train_index, test_index in splitter.split(train):
        train_part, test_part = train.iloc[train_index], train.iloc[test_index]
        linear = LinearRegression().fit(train_part[FEATURE_COLUMNS], train_part["target_next_price"])
        xgb = XGBRegressor(n_estimators=120, max_depth=3, learning_rate=0.05, subsample=0.9, objective="reg:squarederror", random_state=42, n_jobs=1)
        xgb.fit(train_part[FEATURE_COLUMNS], train_part["target_next_price"])
        predictions = {
            "Linear Regression": linear.predict(test_part[FEATURE_COLUMNS]),
            "XGBoost Regressor": xgb.predict(test_part[FEATURE_COLUMNS]),
            "Persistence (naive)": np.repeat(train_part["price_usd"].iloc[-1], len(test_part)),
        }
        try:
            arima_prediction = ARIMA(train_part["price_usd"], order=(1, 1, 1)).fit().forecast(steps=len(test_part))
            predictions["ARIMA(1,1,1)"] = np.asarray(arima_prediction)
        except (ValueError, np.linalg.LinAlgError):
            predictions["ARIMA(1,1,1)"] = np.repeat(train_part["price_usd"].iloc[-1], len(test_part))
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
    train = frame.dropna(subset=FEATURE_COLUMNS + ["target_next_price"])
    if len(train) < 20:
        return []
    model = XGBRegressor(n_estimators=160, max_depth=3, learning_rate=0.05, subsample=0.9, objective="reg:squarederror", random_state=42, n_jobs=1)
    model.fit(train[FEATURE_COLUMNS], train["target_next_price"])
    importance = sorted(zip(FEATURE_COLUMNS, model.feature_importances_), key=lambda pair: pair[1], reverse=True)
    return [{"feature": feature, "importance": round(float(value), 4)} for feature, value in importance]


def _forecast(frame: pd.DataFrame, selected_model: str, steps: int = 7) -> tuple[list[dict], float, str]:
    train = frame.dropna(subset=FEATURE_COLUMNS + ["target_next_price"]).copy()
    use_arima = steps > LONG_HORIZON_STEPS or selected_model == "ARIMA(1,1,1)"
    method = "ARIMA(1,1,1)" if use_arima else selected_model
    model = XGBRegressor(n_estimators=160, max_depth=3, learning_rate=0.05, subsample=0.9, objective="reg:squarederror", random_state=42, n_jobs=1)
    if selected_model == "Linear Regression":
        model = LinearRegression()
    if use_arima:
        try:
            # ARIMA is used for long horizons because multi-step ARIMA
            # forecasts are designed for direct h-step prediction, whereas
            # recursive tree/linear forecasts compound their own errors.
            fitted = ARIMA(frame["price_usd"], order=(1, 1, 1)).fit()
            predictions = np.asarray(fitted.forecast(steps=steps))
            residual_std = float(np.std(fitted.resid))
        except (ValueError, np.linalg.LinAlgError):
            method = selected_model
            model.fit(train[FEATURE_COLUMNS], train["target_next_price"])
            row = frame.iloc[-1].copy()
            predictions = []
            for _ in range(steps):
                prediction = float(model.predict(pd.DataFrame([row[FEATURE_COLUMNS].to_dict()]))[0])
                predictions.append(prediction)
                row["lag_7"], row["lag_2"], row["lag_1"] = row["lag_2"], row["lag_1"], row["price_usd"]
                row["price_usd"] = prediction
                row["sma_7"] = (float(row["sma_7"]) * 6 + prediction) / 7
                row["sma_30"] = (float(row["sma_30"]) * 29 + prediction) / 30
            residual_std = float(np.std(train["target_next_price"] - model.predict(train[FEATURE_COLUMNS])))
    else:
        model.fit(train[FEATURE_COLUMNS], train["target_next_price"])
        row = frame.iloc[-1].copy()
        predictions = []
        for _ in range(steps):
            prediction = float(model.predict(pd.DataFrame([row[FEATURE_COLUMNS].to_dict()]))[0])
            predictions.append(prediction)
            row["lag_7"], row["lag_2"], row["lag_1"] = row["lag_2"], row["lag_1"], row["price_usd"]
            row["price_usd"] = prediction
            row["sma_7"] = (float(row["sma_7"]) * 6 + prediction) / 7
            row["sma_30"] = (float(row["sma_30"]) * 29 + prediction) / 30
        residual_std = float(np.std(train["target_next_price"] - model.predict(train[FEATURE_COLUMNS])))
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
    comparison, signals = _rolling_evaluation(frame)
    selected_model = comparison[0]["model"] if comparison else "Linear Regression"
    forecast, residual_std, forecast_method = _forecast(frame, selected_model, forecast_days)
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
