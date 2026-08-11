from __future__ import annotations

import threading
import time

from flask import Blueprint, abort, jsonify, request

from app.core.config import settings
from app.data.database import recent_alerts, recent_snapshots, save_snapshots
from app.services.analytics import FEATURE_COLUMNS, analyze_history, build_frame, fit_explainer_model
from app.services.assistant import market_summary
from app.services.backtesting import backtest_strategies
from app.services.comparison import compare_assets
from app.services.data_quality import check_data_quality
from app.services.experiments import record_experiment
from app.services.explainability import explain_prediction, global_importance
from app.services.market_data import (
    MarketDataError,
    fetch_fear_greed_history,
    fetch_market_data,
    fetch_price_history,
)
from app.services.market_regime import detect_regime
from app.services.market_score import market_score
from app.services.model_monitoring import detect_drift, record_run
from app.services.monitoring import create_alerts, create_technical_alerts
from app.services.news import get_news
from app.services.risk import risk_analytics

api = Blueprint("api", __name__)

# The full /market/analysis payload is expensive to recompute (ARIMA order
# selection, rolling model evaluation, XGBoost/SHAP explainer). History prices
# are disk-cached for 4h, so a short TTL cache here removes redundant work on
# the dashboard's 5-minute refresh cycle without ever serving stale data.
_ANALYSIS_CACHE_TTL_SECONDS = 15 * 60
_ANALYSIS_CACHE: dict[tuple, tuple[float, dict]] = {}
_ANALYSIS_CACHE_LOCK = threading.Lock()


def _int_arg(name: str, default: int, low: int, high: int) -> int:
    return max(low, min(request.args.get(name, default=default, type=int), high))


def _frame_for(coin_id: str, days: int):
    """Fetch (cached) history and build the shared feature frame."""
    return build_frame(
        fetch_price_history(coin_id, days),
        fetch_fear_greed_history(max(days, 30)),
    )[0]


@api.get("")
@api.get("/")
def index():
    return jsonify(
        {
            "service": "AI Market Intelligence API",
            "endpoints": {
                "health": "/api/health",
                "overview": "/api/market/overview",
                "market/refresh": "/api/market/refresh",
                "market/snapshots": "/api/market/snapshots",
                "market/comparison": "/api/market/comparison?days=90",
                "market/analysis": "/api/market/analysis/<coin_id>?days=30&forecast_days=7",
                "market/regime": "/api/market/regime/<coin_id>?days=90",
                "market/risk": "/api/market/risk/<coin_id>?days=90",
                "market/backtest": "/api/market/backtest/<coin_id>?days=365",
                "market/score": "/api/market/score/<coin_id>?days=90",
                "market/data-quality": "/api/market/data-quality/<coin_id>?days=90",
                "monitoring/drift": "/api/monitoring/drift?coin_id=",
                "alerts": "/api/alerts",
                "news": "/api/news?limit=30",
                "news/coin": "/api/news/<coin_id>?limit=8",
                "assistant/summary": "/api/assistant/summary?coin_id=bitcoin",
            },
        }
    )


@api.get("/health")
def health():
    return jsonify({"status": "ok"})


@api.post("/market/refresh")
def refresh_market():
    try:
        rows = fetch_market_data()
    except MarketDataError as exc:
        abort(503, description=str(exc))
    saved = save_snapshots(rows)
    alerts = create_alerts(rows)
    return jsonify({"saved": saved, "alerts": alerts, "data": rows})


@api.get("/market/snapshots")
def snapshots():
    coin_id = request.args.get("coin_id")
    limit = max(1, min(request.args.get("limit", default=100, type=int), 1000))
    return jsonify(recent_snapshots(coin_id, limit))


@api.get("/alerts")
def alerts():
    limit = max(1, min(request.args.get("limit", default=20, type=int), 100))
    return jsonify(recent_alerts(limit))


@api.get("/news")
def news():
    """Latest normalized crypto news across all public RSS sources.

    Fully isolated from market data: this endpoint always answers 200, even
    when every feed is unreachable (``error`` carries the per-feed failures).
    """
    limit = _int_arg("limit", 30, 1, 100)
    return jsonify(get_news(limit=limit))


@api.get("/news/<coin_id>")
def news_for_coin(coin_id: str):
    limit = _int_arg("limit", 8, 1, 50)
    payload = get_news(limit=limit, coin_id=coin_id)
    payload["coin_id"] = coin_id
    return jsonify(payload)


@api.get("/assistant/summary")
def assistant_summary():
    coin_id = request.args.get("coin_id")
    rows = recent_snapshots(coin_id, 1)
    if not rows:
        abort(404, description="No saved snapshot for this coin. Refresh data first.")
    return jsonify({"coin_id": coin_id, "summary": market_summary(rows[0])})


@api.get("/market/overview")
def overview():
    """Market overview: latest snapshot per asset, Fear & Greed and recent alerts."""
    snapshots = recent_snapshots(limit=1000)
    latest: dict[str, dict] = {}
    for row in snapshots:
        if row["coin_id"] not in latest:
            latest[row["coin_id"]] = row
    fear_greed = fetch_fear_greed_history(1)
    fear_greed_value = int(fear_greed[0]["value"]) if fear_greed and fear_greed[0].get("value") else None
    return jsonify(
        {
            "assets": list(latest.values()),
            "fear_greed": {"value": fear_greed_value, "label": _fear_greed_label(fear_greed_value)},
            "alerts": recent_alerts(10),
            "needs_refresh": not latest,
        }
    )


def _fear_greed_label(value: int | None) -> str | None:
    if value is None:
        return None
    if value >= 80:
        return "EXTREME GREED"
    if value >= 60:
        return "GREED"
    if value >= 40:
        return "NEUTRAL"
    if value >= 20:
        return "FEAR"
    return "EXTREME FEAR"


@api.get("/market/analysis/<coin_id>")
def market_analysis(coin_id):
    days = _int_arg("days", 30, 1, 365)
    forecast_days = _int_arg("forecast_days", 7, 1, 1095)
    try:
        result = _analysis_for(coin_id, days, forecast_days)
    except MarketDataError as exc:
        abort(503, description=str(exc))
    record_experiment(
        coin_id,
        days,
        result["model_comparison"],
        result["metrics"]["selected_model"],
        forecast_days=forecast_days,
        metrics=result["metrics"],
    )
    best = result["model_comparison"][0] if result["model_comparison"] else {}
    record_run(
        coin_id,
        result["metrics"]["selected_model"],
        best.get("mae", 0) or 0,
        best.get("rmse", 0) or 0,
        best.get("directional_accuracy", 0) or 0,
        days,
        len(FEATURE_COLUMNS),
    )
    return jsonify(result)


def _analysis_for(coin_id: str, days: int, forecast_days: int) -> dict:
    """Compute or fetch the cached full analysis payload for one asset.

    Raises ``MarketDataError`` when history is unavailable so the route can
    answer 503; a background warm thread uses the same path at startup.
    """
    key = (coin_id, days, forecast_days)
    now = time.time()
    with _ANALYSIS_CACHE_LOCK:
        cached = _ANALYSIS_CACHE.get(key)
        if cached and now - cached[0] < _ANALYSIS_CACHE_TTL_SECONDS:
            return cached[1]
    frame, _candles = build_frame(
        fetch_price_history(coin_id, days),
        fetch_fear_greed_history(max(days, 30)),
    )
    result = analyze_history(
        fetch_price_history(coin_id, days),
        fetch_fear_greed_history(max(days, 30)),
        forecast_days=forecast_days,
    )
    result["technical_alerts"] = create_technical_alerts(coin_id, frame)
    try:
        model, X = fit_explainer_model(frame, result["metrics"]["selected_model"])
        result["explanation"] = {
            "local": explain_prediction(model, X, index=-1, model_kind="linear" if result["metrics"]["selected_model"] == "Linear Regression" else "xgboost"),
            "global": global_importance(model, X, model_kind="linear" if result["metrics"]["selected_model"] == "Linear Regression" else "xgboost"),
        }
    except Exception:
        result["explanation"] = None
    with _ANALYSIS_CACHE_LOCK:
        _ANALYSIS_CACHE[key] = (time.time(), result)
    return result


def warm_caches() -> None:
    """Background startup warm: news feeds plus the default coin's analysis,
    so the first dashboard load doesn't pay the cold costs."""
    from app.core.config import settings as _settings

    default_coin = _settings.tracked_coins[0]
    try:
        _analysis_for(default_coin, 365, 7)
    except Exception:
        pass
    try:
        get_news(limit=100)
    except Exception:
        pass


@api.get("/market/regime/<coin_id>")
def regime(coin_id):
    days = _int_arg("days", 90, 30, 365)
    try:
        frame = _frame_for(coin_id, days)
    except MarketDataError as exc:
        abort(503, description=str(exc))
    return jsonify({"coin_id": coin_id, **detect_regime(frame)})


@api.get("/market/risk/<coin_id>")
def risk(coin_id):
    days = _int_arg("days", 90, 30, 365)
    try:
        frame = _frame_for(coin_id, days)
    except MarketDataError as exc:
        abort(503, description=str(exc))
    return jsonify({"coin_id": coin_id, **risk_analytics(frame)})


@api.get("/market/backtest/<coin_id>")
def backtest(coin_id):
    days = _int_arg("days", 365, 90, 365)
    try:
        frame = _frame_for(coin_id, days)
    except MarketDataError as exc:
        abort(503, description=str(exc))
    try:
        return jsonify({"coin_id": coin_id, **backtest_strategies(frame)})
    except ValueError as exc:
        abort(422, description=str(exc))


@api.get("/market/score/<coin_id>")
def score(coin_id):
    days = _int_arg("days", 90, 30, 365)
    try:
        frame = _frame_for(coin_id, days)
    except MarketDataError as exc:
        abort(503, description=str(exc))
    try:
        return jsonify({"coin_id": coin_id, **market_score(frame)})
    except ValueError as exc:
        abort(422, description=str(exc))


@api.get("/market/comparison")
def comparison():
    days = _int_arg("days", 90, 30, 365)
    frames: dict[str, object] = {}
    for coin_id in settings.tracked_coins:
        try:
            frames[coin_id] = _frame_for(coin_id, days)
        except MarketDataError as exc:
            frames[coin_id] = None
            # keep going: comparison should degrade gracefully per asset
            _ = exc
    frames = {coin_id: frame for coin_id, frame in frames.items() if frame is not None}
    try:
        return jsonify(compare_assets(frames))
    except ValueError as exc:
        abort(422, description=str(exc))


@api.get("/market/data-quality/<coin_id>")
def data_quality(coin_id):
    days = _int_arg("days", 90, 30, 365)
    try:
        history = fetch_price_history(coin_id, days)
        fear_greed = fetch_fear_greed_history(max(days, 30))
    except MarketDataError as exc:
        abort(503, description=str(exc))
    return jsonify({"coin_id": coin_id, **check_data_quality(history, fear_greed)})


@api.get("/monitoring/drift")
def drift():
    coin_id = request.args.get("coin_id")
    return jsonify({"coin_id": coin_id, **detect_drift(coin_id)})
