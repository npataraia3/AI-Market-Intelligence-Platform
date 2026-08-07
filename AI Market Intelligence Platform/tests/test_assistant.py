from app.services.assistant import market_summary
from app.services.analytics import analyze_history
from app.services.reporting import build_monthly_excel_report


def test_market_summary_reports_direction() -> None:
    text = market_summary({"name": "Bitcoin", "price_usd": 100_000, "change_24h_percent": 6})
    assert "strong upward movement" in text
    assert "$100,000.00" in text


def test_history_analysis_has_indicators_and_forecast() -> None:
    history = {
        "prices": [[1_700_000_000_000 + i * 86_400_000, 100 + i] for i in range(20)],
        "total_volumes": [[1_700_000_000_000 + i * 86_400_000, 1_000 + i] for i in range(20)],
    }
    result = analyze_history(history)
    assert result["metrics"]["trend"] == "bullish"
    assert len(result["forecast"]) == 7


def test_excel_report_is_created() -> None:
    history = {
        "prices": [[1_700_000_000_000 + i * 86_400_000, 100 + i] for i in range(20)],
        "total_volumes": [[1_700_000_000_000 + i * 86_400_000, 1_000 + i] for i in range(20)],
    }
    workbook = build_monthly_excel_report("Bitcoin (BTC)", "bitcoin", analyze_history(history), "Test summary")
    assert workbook[:2] == b"PK"  # XLSX files are ZIP containers.
