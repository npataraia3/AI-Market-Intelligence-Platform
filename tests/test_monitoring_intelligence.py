import numpy as np
import pytest

from app.services.analytics import build_frame
from app.services import model_monitoring
from app.services import monitoring


def _history(days: int = 90, drift: float = 0.0, noise: float = 0.02) -> dict:
    rng = np.random.default_rng(3)
    t0 = 1_700_000_000_000
    prices = []
    volumes = []
    for i in range(days):
        price = 100 * (1 + drift) ** i * (1 + noise * rng.standard_normal())
        prices.append([t0 + i * 86_400_000, price])
        volumes.append([t0 + i * 86_400_000, 1_000 + i * 10])
    return {"prices": prices, "total_volumes": volumes}


def _frame(days: int = 90, drift: float = 0.0, noise: float = 0.02) -> object:
    return build_frame(_history(days, drift, noise))[0]


def _fill_runs(monkeypatch, tmp_path, mae_values) -> None:
    runs_file = tmp_path / "model_runs.jsonl"
    monkeypatch.setattr(model_monitoring, "RUNS_FILE", runs_file)
    for i, mae in enumerate(mae_values):
        model_monitoring.record_run(
            coin_id="bitcoin",
            selected_model=f"XGBoost-{i}",
            mae=mae,
            rmse=mae * 1.3,
            directional_accuracy=0.5 + (i % 3) / 10,
            history_days=90,
            feature_count=12,
        )


def test_record_run_and_performance_over_time(monkeypatch, tmp_path) -> None:
    _fill_runs(monkeypatch, tmp_path, [100, 110, 95, 90, 120])
    series = model_monitoring.performance_over_time("bitcoin")
    assert len(series) == 5
    assert all(entry["selected_model"].startswith("XGBoost") for entry in series)
    assert series[0]["mae"] == 120  # newest run first


def test_detect_drift_stable(monkeypatch, tmp_path) -> None:
    _fill_runs(monkeypatch, tmp_path, [100, 105, 95, 100, 102, 98, 103, 97])
    result = model_monitoring.detect_drift("bitcoin")
    assert result["drifted"] is False


def test_detect_drift_triggers(monkeypatch, tmp_path) -> None:
    _fill_runs(monkeypatch, tmp_path, [100, 102, 98, 100, 300, 310, 290, 305])
    result = model_monitoring.detect_drift("bitcoin")
    assert result["drifted"] is True
    assert result["recent_mae"] > result["baseline_mae"]
    assert result["ratio"] >= model_monitoring.DRIFT_THRESHOLD


def test_detect_drift_insufficient_runs(monkeypatch, tmp_path) -> None:
    _fill_runs(monkeypatch, tmp_path, [100, 110])
    result = model_monitoring.detect_drift("bitcoin")
    assert result["drifted"] is False
    assert result["status"] == "insufficient data"


def test_technical_alerts_rsi_overbought(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(monitoring, "REGIME_STATE_FILE", tmp_path / "regime_state.json")
    frame = _frame(90, drift=0.004, noise=0.0)  # pure uptrend -> RSI near 100
    alerts = monitoring.create_technical_alerts("bitcoin", frame)
    types = {alert["type"] for alert in alerts}
    assert "rsi" in types
    assert all(alert["coin_id"] == "bitcoin" for alert in alerts)
    assert all(alert["severity"] in {"low", "medium", "high"} for alert in alerts)


def test_technical_alerts_insufficient_data() -> None:
    frame = _frame(5)
    assert monitoring.create_technical_alerts("bitcoin", frame) == []


def test_price_alerts_preserved() -> None:
    rows = [
        {"id": "bitcoin", "name": "Bitcoin", "price_change_percentage_24h": 8.4},
        {"id": "ethereum", "name": "Ethereum", "price_change_percentage_24h": -6.2},
        {"id": "solana", "name": "Solana", "price_change_percentage_24h": 1.1},
    ]
    alerts = monitoring.create_alerts(rows)
    assert len(alerts) == 2
    assert all(alert["severity"] in {"low", "medium", "high"} for alert in alerts)
    assert {alert["coin_id"] for alert in alerts} == {"bitcoin", "ethereum"}
