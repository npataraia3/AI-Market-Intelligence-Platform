from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.data.database import recent_alerts, recent_snapshots, save_snapshots
from app.services.assistant import market_summary
from app.services.analytics import analyze_history
from app.services.experiments import record_experiment
from app.services.market_data import MarketDataError, fetch_fear_greed_history, fetch_market_data, fetch_price_history
from app.services.monitoring import create_alerts

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.post("/market/refresh")
def refresh_market() -> dict:
    try:
        rows = fetch_market_data()
    except MarketDataError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    save_snapshots(rows)
    alerts = create_alerts(rows)
    return {"saved": len(rows), "alerts": alerts, "data": rows}


@router.get("/market/snapshots")
def snapshots(coin_id: str | None = None, limit: int = Query(100, ge=1, le=1000)) -> list[dict]:
    return recent_snapshots(coin_id, limit)


@router.get("/alerts")
def alerts(limit: int = Query(20, ge=1, le=100)) -> list[dict]:
    return recent_alerts(limit)


@router.get("/assistant/summary")
def assistant_summary(coin_id: str) -> dict:
    rows = recent_snapshots(coin_id, 1)
    if not rows:
        raise HTTPException(status_code=404, detail="No saved snapshot for this coin. Refresh data first.")
    return {"coin_id": coin_id, "summary": market_summary(rows[0])}


@router.get("/market/analysis/{coin_id}")
def market_analysis(
    coin_id: str,
    days: int = Query(30, ge=1, le=365),
    forecast_days: int = Query(7, ge=1, le=1095),
) -> dict:
    try:
        result = analyze_history(
            fetch_price_history(coin_id, days),
            fetch_fear_greed_history(max(days, 30)),
            forecast_days=forecast_days,
        )
        record_experiment(coin_id, days, result["model_comparison"], result["metrics"]["selected_model"], forecast_days=forecast_days, metrics=result["metrics"])
        return result
    except MarketDataError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
