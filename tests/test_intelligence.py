import numpy as np
import pytest
from datetime import datetime, timezone

from app.services.analytics import build_frame
from app.services.backtesting import backtest_strategies
from app.services.comparison import compare_assets
from app.services.data_quality import check_data_quality
from app.services.explainability import explain_prediction, global_importance
from app.services.market_regime import detect_regime
from app.services.market_score import market_score
from app.services.risk import risk_analytics


def _history(days: int = 120, drift: float = 0.0, noise: float = 0.0, start: float = 100.0) -> dict:
    rng = np.random.default_rng(7)
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    t0 = end_ms - (days - 1) * 86_400_000
    prices = []
    volumes = []
    for i in range(days):
        shock = 1 + noise * rng.standard_normal()
        price = start * (1 + drift) ** i * shock
        prices.append([t0 + i * 86_400_000, price])
        volumes.append([t0 + i * 86_400_000, 1_000 + i * 10])
    return {"prices": prices, "total_volumes": volumes}


def _frame(days: int = 120, drift: float = 0.0, noise: float = 0.0) -> object:
    return build_frame(_history(days, drift, noise))[0]


def test_rule_based_regime_bull_on_uptrend() -> None:
    frame = _frame(120, drift=0.005)
    regime = detect_regime(frame)["rule_based"]
    assert regime["trend"] == "BULL"
    assert regime["regime"].startswith("BULL")
    assert regime["evidence"]["return_30d_percent"] > 0


def test_rule_based_regime_bear_on_downtrend() -> None:
    frame = _frame(120, drift=-0.005)
    regime = detect_regime(frame)["rule_based"]
    assert regime["trend"] == "BEAR"


def test_regime_insufficient_data() -> None:
    frame = _frame(3)
    assert detect_regime(frame)["rule_based"]["regime"] == "INSUFFICIENT DATA"


def test_regime_kmeans_returns_clusters() -> None:
    frame = _frame(200, drift=0.004, noise=0.02)
    result = detect_regime(frame)
    assert result["unsupervised"]["available"] is True
    assert result["unsupervised"]["clusters"]
    assert result["consensus"]


def test_risk_metrics_are_reasonable() -> None:
    frame = _frame(200, drift=0.002, noise=0.02)
    risk = risk_analytics(frame)
    assert risk["max_drawdown_percent"] <= 0
    assert -10 < risk["var"]["historical_var_percent"] < 0
    assert risk["var"]["cvar_percent"] <= risk["var"]["historical_var_percent"]
    assert risk["ratios"]["sharpe"] is not None
    assert risk["drawdown_series"]


def test_risk_requires_data() -> None:
    with pytest.raises(ValueError):
        risk_analytics(build_frame({"prices": [], "total_volumes": []})[0])


def test_backtest_runs_all_strategies() -> None:
    frame = _frame(300, drift=0.003, noise=0.02)
    result = backtest_strategies(frame)
    names = {row["strategy"] for row in result["results"]}
    assert "Buy & Hold" in names
    assert "XGBoost signal" in names
    assert result["cost_per_trade_percent"] == 0.2
    assert result["equity_curves"]


def test_backtest_needs_history() -> None:
    with pytest.raises(ValueError):
        backtest_strategies(_frame(30))


def test_market_score_transparent_components() -> None:
    frame = _frame(120, drift=0.005, noise=0.01)
    result = market_score(frame)
    assert 0 <= result["score"] <= 100
    names = {component["name"] for component in result["components"]}
    assert {"Momentum", "Trend", "Sentiment", "Volume", "Volatility", "RSI"} <= names
    total = sum(component["points"] for component in result["components"])
    assert abs(result["score"] - max(0.0, min(100.0, 50 + total))) < 0.01


def test_market_score_requires_data() -> None:
    with pytest.raises(ValueError):
        market_score(_frame(4))


def test_data_quality_clean_payload() -> None:
    result = check_data_quality(_history(90))
    assert result["healthy"] is True
    names = {check["check"] for check in result["checks"]}
    assert {"schema", "missing_values", "duplicates", "freshness"} <= names


def test_data_quality_flags_duplicates_and_jumps() -> None:
    history = _history(90)
    history["prices"][5][0] = history["prices"][4][0]  # duplicate timestamp
    history["prices"][20][1] = history["prices"][19][1] * 20  # huge jump
    result = check_data_quality(history)
    statuses = {check["check"]: check["status"] for check in result["checks"]}
    assert statuses["duplicates"] == "WARN"
    assert statuses["price_jumps"] == "WARN"
    assert result["issues"]


def test_data_quality_missing_schema() -> None:
    result = check_data_quality({"prices": []})
    assert result["healthy"] is False


def test_comparison_across_assets() -> None:
    frames = {
        "bitcoin": _frame(120, drift=0.004),
        "ethereum": _frame(120, drift=0.001, noise=0.02),
        "solana": _frame(120, drift=0.002, noise=0.04),
    }
    result = compare_assets(frames)
    assert len(result["coins"]) == 3
    assert result["correlation_matrix"]
    assert result["series"]["normalized_performance"]
    assert result["rolling_correlation"]


def test_explainability_xgboost_shap() -> None:
    from xgboost import XGBRegressor

    frame = _frame(120, drift=0.003, noise=0.02)
    train = frame.dropna(subset=["lag_1", "lag_2", "lag_7", "return_1", "return_7", "sma_7", "sma_30", "rsi_14", "volatility_14", "volume_usd", "vwap", "fear_greed", "next_return"])
    X = train[["lag_1", "lag_2", "lag_7", "return_1", "return_7", "sma_7", "sma_30", "rsi_14", "volatility_14", "volume_usd", "vwap", "fear_greed"]]
    model = XGBRegressor(n_estimators=40, max_depth=3, n_jobs=1, random_state=42)
    model.fit(X, train["next_return"])
    local = explain_prediction(model, X, index=-1)
    assert local["method"].startswith("SHAP")
    assert local["contributions"]
    g = global_importance(model, X)
    assert g["features"]
    assert all(np.isfinite(item["importance"]) for item in g["features"])
