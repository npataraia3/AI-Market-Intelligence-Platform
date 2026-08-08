from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

EXPERIMENT_FILE = Path("logs/model_experiments.jsonl")


def record_experiment(
    coin_id: str,
    days: int,
    comparison: list[dict],
    selected_model: str,
    forecast_days: int = 7,
    metrics: dict | None = None,
) -> None:
    """Persist reproducible local model metrics and log the same run to MLflow.

    The JSONL file keeps the pipeline dependency-free and readable; MLflow
    mirrors the same run for optional local experiment tracking via `mlflow ui`.
    """
    EXPERIMENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "run_at": datetime.now(timezone.utc).isoformat(), "coin_id": coin_id,
        "history_days": days, "forecast_days": forecast_days,
        "selected_model": selected_model, "models": comparison,
    }
    with EXPERIMENT_FILE.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record) + "\n")

    try:
        import mlflow

        mlflow.set_tracking_uri("sqlite:///mlflow.db")
        experiment = mlflow.set_experiment("market-analysis")
        with mlflow.start_run(run_name=f"{coin_id}-{days}d", experiment_id=experiment.experiment_id):
            mlflow.log_param("coin_id", coin_id)
            mlflow.log_param("history_days", days)
            mlflow.log_param("forecast_days", forecast_days)
            mlflow.log_param("selected_model", selected_model)
            for model in comparison:
                safe_name = "".join(char if char.isalnum() else "_" for char in model["model"]).strip("_")
                mlflow.log_metric(f"{safe_name}_mae", model["mae"])
                mlflow.log_metric(f"{safe_name}_rmse", model["rmse"])
                mlflow.log_metric(f"{safe_name}_folds", model["folds"])
            if metrics:
                for key, value in metrics.items():
                    if type(value) in (int, float):
                        mlflow.log_metric(key, value)
    except Exception as exc:
        logger.warning("MLflow tracking unavailable: %s", exc)
