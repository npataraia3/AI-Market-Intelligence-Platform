from app.services.analytics import analyze_history
from app.services.reporting import build_analysis_excel_report, build_forecast_excel_report


def _history(days: int = 30) -> dict:
    return {
        "prices": [[1_700_000_000_000 + i * 86_400_000, 100 + i] for i in range(days)],
        "total_volumes": [[1_700_000_000_000 + i * 86_400_000, 1_000 + i] for i in range(days)],
    }


def test_analysis_report_builds_for_any_period() -> None:
    result = analyze_history(_history(90))
    workbook = build_analysis_excel_report("Bitcoin (BTC)", "bitcoin", result, "Test summary", days=90)
    assert workbook[:2] == b"PK"


def test_analysis_report_keeps_30_day_wrapper() -> None:
    result = analyze_history(_history(30))
    workbook = build_analysis_excel_report("Bitcoin (BTC)", "bitcoin", result, "Test summary")
    assert workbook[:2] == b"PK"


def test_forecast_excel_report_is_created() -> None:
    result = analyze_history(_history(90), forecast_days=30)
    workbook = build_forecast_excel_report("Bitcoin (BTC)", "bitcoin", result["forecast"], result["metrics"]["forecast_method"], 30)
    assert workbook[:2] == b"PK"


def test_forecast_length_follows_requested_horizon() -> None:
    for horizon in (30, 90, 365, 1095):
        result = analyze_history(_history(730), forecast_days=horizon)
        assert len(result["forecast"]) == horizon


def test_model_comparison_includes_naive_baseline() -> None:
    result = analyze_history(_history(730))
    models = {row["model"] for row in result["model_comparison"]}
    assert "Persistence (naive)" in models


def test_feature_importance_is_returned() -> None:
    result = analyze_history(_history(730))
    assert result["feature_importance"]
    assert {"feature", "importance"} <= result["feature_importance"][0].keys()


def test_metrics_report_forecast_method() -> None:
    result = analyze_history(_history(730), forecast_days=30)
    method = result["metrics"]["forecast_method"]
    assert method in {"Linear Regression", "XGBoost Regressor", "Persistence (naive)"} or method.startswith("ARIMA(")


def test_long_horizon_uses_arima_method() -> None:
    result = analyze_history(_history(730), forecast_days=365)
    assert result["metrics"]["forecast_method"].startswith("ARIMA(")
