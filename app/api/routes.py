from __future__ import annotations

from flask import Blueprint, abort, jsonify, request

from app.data.database import recent_alerts, recent_snapshots, save_snapshots
from app.services.analytics import analyze_history
from app.services.assistant import market_summary
from app.services.experiments import record_experiment
from app.services.market_data import (
    MarketDataError,
    fetch_fear_greed_history,
    fetch_market_data,
    fetch_price_history,
)
from app.services.monitoring import create_alerts

api = Blueprint("api", __name__)


@api.get("")
@api.get("/")
def index():
    return jsonify(
        {
            "service": "AI Market Intelligence API",
            "endpoints": {
                "health": "/api/health",
                "market/refresh": "/api/market/refresh",
                "market/snapshots": "/api/market/snapshots",
                "alerts": "/api/alerts",
                "assistant/summary": "/api/assistant/summary",
                "market/analysis": "/api/market/analysis/<coin_id>?days=30&forecast_days=7",
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


@api.get("/assistant/summary")
def assistant_summary():
    coin_id = request.args.get("coin_id")
    rows = recent_snapshots(coin_id, 1)
    if not rows:
        abort(404, description="No saved snapshot for this coin. Refresh data first.")
    return jsonify({"coin_id": coin_id, "summary": market_summary(rows[0])})


@api.get("/market/analysis/<coin_id>")
def market_analysis(coin_id):
    days = max(1, min(request.args.get("days", default=30, type=int), 365))
    forecast_days = max(1, min(request.args.get("forecast_days", default=7, type=int), 1095))
    try:
        result = analyze_history(
            fetch_price_history(coin_id, days),
            fetch_fear_greed_history(max(days, 30)),
            forecast_days=forecast_days,
        )
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
    return jsonify(result)
