from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

RUNS_FILE = Path("logs/model_runs.jsonl")
DRIFT_WINDOW = 3
BASELINE_WINDOW = 5
DRIFT_THRESHOLD = 1.25  # recent MAE > 125% of baseline -> drift


def _read_runs(coin_id: str | None = None) -> list[dict]:
    if not RUNS_FILE.exists():
        return []
    records: list[dict] = []
    try:
        for line in RUNS_FILE.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if coin_id is None or record.get("coin_id") == coin_id:
                records.append(record)
    except (OSError, ValueError) as exc:
        logger.warning("Unable to read model runs log: %s", exc)
    return records


def record_run(coin_id: str, selected_model: str, mae: float, rmse: float, directional_accuracy: float, history_days: int, feature_count: int) -> None:
    """Persist a single model run for drift and performance-over-time tracking."""
    RUNS_FILE.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "coin_id": coin_id,
        "selected_model": selected_model,
        "mae": round(float(mae), 4),
        "rmse": round(float(rmse), 4),
        "directional_accuracy": round(float(directional_accuracy), 4),
        "history_days": int(history_days),
        "feature_count": int(feature_count),
    }
    try:
        with RUNS_FILE.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record) + "\n")
    except OSError as exc:
        logger.warning("Unable to write model run: %s", exc)


def performance_over_time(coin_id: str | None = None, limit: int = 20) -> list[dict]:
    """Latest recorded runs, newest first, with an MAE-change note per run."""
    runs = _read_runs(coin_id)[-limit:]
    runs.reverse()
    for index, run in enumerate(runs):
        if index + DRIFT_WINDOW < len(runs):
            baseline = [other["mae"] for other in runs[index + DRIFT_WINDOW:index + DRIFT_WINDOW + BASELINE_WINDOW]]
            change = run["mae"] / max(1e-9, sum(baseline) / len(baseline))
            run["mae_change_vs_baseline"] = round(change, 3)
        else:
            run["mae_change_vs_baseline"] = None
    return runs


def detect_drift(coin_id: str | None = None) -> dict:
    """Compare the most recent runs against a longer baseline and flag drift."""
    runs = _read_runs(coin_id)
    if len(runs) < DRIFT_WINDOW + 3:
        return {"status": "insufficient data", "drifted": False, "detail": f"Need at least {DRIFT_WINDOW + 3} runs for {coin_id or 'all coins'}."}
    recent = [run["mae"] for run in runs[-DRIFT_WINDOW:]]
    baseline = [run["mae"] for run in runs[-DRIFT_WINDOW - BASELINE_WINDOW:-DRIFT_WINDOW]]
    recent_mae = sum(recent) / len(recent)
    baseline_mae = sum(baseline) / len(baseline)
    ratio = recent_mae / max(1e-9, baseline_mae)
    drifted = ratio > DRIFT_THRESHOLD
    detail = (
        f"Recent {DRIFT_WINDOW}-run MAE {recent_mae:.0f} is {ratio:.0%} of the "
        f"{BASELINE_WINDOW}-run baseline ({baseline_mae:.0f}). "
        + ("MODEL DRIFT DETECTED — consider retraining." if drifted else "No significant degradation.")
    )
    return {
        "status": "drift" if drifted else "ok",
        "drifted": drifted,
        "recent_mae": round(recent_mae, 2),
        "baseline_mae": round(baseline_mae, 2),
        "ratio": round(ratio, 3),
        "detail": detail,
        "runs": performance_over_time(coin_id),
    }
