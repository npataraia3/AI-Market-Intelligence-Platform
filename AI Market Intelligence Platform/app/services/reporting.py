from __future__ import annotations

from io import BytesIO

import pandas as pd


def build_analysis_excel_report(coin_name: str, coin_id: str, analysis: dict, summary: str, days: int = 30) -> bytes:
    """Build a formatted, self-contained analysis workbook for the selected period."""
    output = BytesIO()
    metrics = analysis["metrics"]
    series = pd.DataFrame(analysis["series"])
    candles = pd.DataFrame(analysis["candles"])
    forecast = pd.DataFrame(analysis["forecast"])
    source_url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days={days}"

    with pd.ExcelWriter(output, engine="xlsxwriter", datetime_format="yyyy-mm-dd hh:mm") as writer:
        workbook = writer.book
        title = workbook.add_format({"bold": True, "font_size": 18, "font_color": "#FFFFFF", "bg_color": "#1565C0"})
        section = workbook.add_format({"bold": True, "font_color": "#FFFFFF", "bg_color": "#6A1B9A"})
        label = workbook.add_format({"bold": True, "font_color": "#1565C0"})
        currency = workbook.add_format({"num_format": '$#,##0.00;[Red]($#,##0.00);-'})
        percentage = workbook.add_format({"num_format": '0.00%;[Red](0.00%);-'})
        number = workbook.add_format({"num_format": '#,##0.00;[Red](#,##0.00);-'})
        note = workbook.add_format({"italic": True, "font_color": "#666666", "text_wrap": True})
        green = workbook.add_format({"font_color": "#2E7D32", "bold": True})

        summary_sheet = workbook.add_worksheet("Summary")
        writer.sheets["Summary"] = summary_sheet
        summary_sheet.hide_gridlines(2)
        summary_sheet.set_column("A:A", 24)
        summary_sheet.set_column("B:B", 20)
        summary_sheet.set_column("C:C", 55)
        summary_sheet.merge_range("A1:C1", f"{coin_name} — Detailed {days}-Day Market Analysis", title)
        summary_sheet.write("A3", "Metric", section)
        summary_sheet.write("B3", "Value", section)
        summary_rows = [
            ("Current price (USD)", metrics["current_price"], currency),
            ("SMA 7 (USD)", metrics["sma_7"], currency),
            ("SMA 30 (USD)", metrics["sma_30"], currency),
            ("RSI (14)", metrics["rsi_14"], number),
            ("RSI state", metrics["rsi_state"].title(), None),
            ("Trend", metrics["trend"].title(), None),
            ("Volatility", metrics["volatility_percent"] / 100, percentage),
            ("Selected forecast model", metrics.get("selected_model", "Linear Regression"), None),
            ("Fear & Greed Index", metrics.get("fear_greed"), number),
            ("VWAP (USD)", metrics.get("vwap"), currency),
        ]
        for index, (metric, value, value_format) in enumerate(summary_rows, start=3):
            summary_sheet.write(index, 0, metric, label)
            if value is None:
                summary_sheet.write(index, 1, "Not enough data")
            else:
                summary_sheet.write(index, 1, value, value_format)
        summary_sheet.write("A14", "Market assistant", section)
        summary_sheet.merge_range("A15:C17", summary, note)
        summary_sheet.write("A19", "Source", section)
        summary_sheet.write_url("A20", source_url, string="CoinGecko market_chart API (retrieved on report generation)", cell_format=green)
        summary_sheet.merge_range("A22:C23", "Educational analysis only — this report is not financial or investment advice. The forecast is a simple linear-regression baseline.", note)
        summary_sheet.merge_range("A25:C26", "Number formats: values shown in red parentheses (e.g. (1,234.56)) are negative — a standard Excel accounting format. A negative forecast lower bound is not an error: at long horizons the 95% interval is so wide it extends below zero, i.e. the price could theoretically fall to $0.", note)

        series["timestamp"] = pd.to_datetime(series["timestamp"], utc=True).dt.tz_localize(None)
        series.to_excel(writer, sheet_name="Price History", index=False, startrow=1)
        price_sheet = writer.sheets["Price History"]
        price_sheet.hide_gridlines(2)
        price_sheet.freeze_panes(2, 0)
        price_sheet.write("A1", "Price History with Technical Indicators", title)
        price_sheet.set_column("A:A", 20, workbook.add_format({"num_format": "yyyy-mm-dd hh:mm"}))
        price_sheet.set_column("B:D", 16, currency)
        price_sheet.set_column("E:E", 16, currency)
        price_sheet.set_column("F:F", 12, number)
        price_sheet.autofilter(1, 0, len(series) + 1, len(series.columns) - 1)

        candles.to_excel(writer, sheet_name="Candlesticks", index=False, startrow=1)
        candle_sheet = writer.sheets["Candlesticks"]
        candle_sheet.hide_gridlines(2)
        candle_sheet.freeze_panes(2, 0)
        candle_sheet.write("A1", "Daily OHLC Candlesticks and Volume", title)
        candle_sheet.set_column("A:A", 14)
        candle_sheet.set_column("B:F", 17, currency)
        candle_sheet.autofilter(1, 0, len(candles) + 1, len(candles.columns) - 1)

        forecast["timestamp"] = pd.to_datetime(forecast["timestamp"], utc=True).dt.tz_localize(None)
        forecast.to_excel(writer, sheet_name="Forecast", index=False, startrow=1)
        forecast_sheet = writer.sheets["Forecast"]
        forecast_sheet.hide_gridlines(2)
        forecast_sheet.write("A1", f"{len(forecast)}-Day Baseline Forecast", title)
        forecast_sheet.set_column("A:A", 20, workbook.add_format({"num_format": "yyyy-mm-dd"}))
        forecast_sheet.set_column("B:B", 18, currency)
        forecast_sheet.autofilter(1, 0, len(forecast) + 1, len(forecast.columns) - 1)

        chart = workbook.add_chart({"type": "line"})
        chart.add_series({"name": "Price", "categories": ["Price History", 2, 0, len(series) + 1, 0], "values": ["Price History", 2, 1, len(series) + 1, 1], "line": {"color": "#1565C0", "width": 2.25}})
        chart.add_series({"name": "SMA 7", "categories": ["Price History", 2, 0, len(series) + 1, 0], "values": ["Price History", 2, 3, len(series) + 1, 3], "line": {"color": "#C69214", "width": 1.5}})
        chart.set_title({"name": "Price and SMA 7"})
        chart.set_y_axis({"name": "USD", "num_format": "$#,##0"})
        chart.set_legend({"position": "bottom"})
        summary_sheet.insert_chart("E3", chart, {"x_scale": 1.4, "y_scale": 1.35})
    return output.getvalue()


def build_monthly_excel_report(coin_name: str, coin_id: str, analysis: dict, summary: str) -> bytes:
    """Backwards-compatible wrapper for the 30-day analysis workbook."""
    return build_analysis_excel_report(coin_name, coin_id, analysis, summary, days=30)


def build_forecast_excel_report(coin_name: str, coin_id: str, forecast: list[dict], selected_model: str, horizon_days: int) -> bytes:
    """Build a formatted Excel workbook containing the price forecast for the requested horizon."""
    output = BytesIO()
    frame = pd.DataFrame(forecast)
    if frame.empty:
        frame = pd.DataFrame(columns=["timestamp", "price_usd", "lower_95", "upper_95"])
    frame = frame.rename(columns={
        "timestamp": "Date", "price_usd": "Predicted price (USD)",
        "lower_95": "95% lower bound", "upper_95": "95% upper bound",
    })
    frame["Date"] = pd.to_datetime(frame["Date"], utc=True).dt.tz_localize(None)

    with pd.ExcelWriter(output, engine="xlsxwriter", datetime_format="yyyy-mm-dd") as writer:
        workbook = writer.book
        title = workbook.add_format({"bold": True, "font_size": 18, "font_color": "#FFFFFF", "bg_color": "#1565C0"})
        section = workbook.add_format({"bold": True, "font_color": "#FFFFFF", "bg_color": "#6A1B9A"})
        note = workbook.add_format({"italic": True, "font_color": "#666666", "text_wrap": True})
        currency = workbook.add_format({"num_format": '$#,##0.00;[Red]($#,##0.00);-'})
        date_format = workbook.add_format({"num_format": "yyyy-mm-dd"})

        sheet = workbook.add_worksheet("Forecast")
        writer.sheets["Forecast"] = sheet
        sheet.hide_gridlines(2)
        sheet.freeze_panes(3, 0)
        sheet.merge_range("A1:D1", f"{coin_name} — {horizon_days}-Day Price Forecast", title)
        sheet.write("A2", f"Baseline model: {selected_model} · Forecast generated on demand from the selected analysis period", note)
        sheet.merge_range(f"A{len(frame) + 4}:D{len(frame) + 4}", "A flat point forecast is expected: prices behave close to a random walk, so the best single estimate is \"around today's price\". The 95% lower/upper bounds widen with the horizon to show the growing uncertainty.", note)
        frame.to_excel(writer, sheet_name="Forecast", index=False, startrow=2)
        sheet.set_column("A:A", 16, date_format)
        sheet.set_column("B:D", 20, currency)
        sheet.autofilter(2, 0, len(frame) + 2, len(frame.columns) - 1)
        sheet.merge_range(f"A{len(frame) + 5}:D{len(frame) + 5}", "Values shown in red parentheses (e.g. (1,234.56)) are negative — a standard Excel accounting format. A negative lower bound at long horizons reflects very wide uncertainty, not an error; prices cannot fall below $0.", note)
        sheet.merge_range(f"A{len(frame) + 6}:D{len(frame) + 7}", "Educational forecast only — this file is not financial or investment advice.", note)

        chart = workbook.add_chart({"type": "line"})
        chart.add_series({"name": "Predicted price", "categories": ["Forecast", 3, 0, len(frame) + 2, 0], "values": ["Forecast", 3, 1, len(frame) + 2, 1], "line": {"color": "#1565C0", "width": 2.5}})
        chart.add_series({"name": "95% lower bound", "categories": ["Forecast", 3, 0, len(frame) + 2, 0], "values": ["Forecast", 3, 2, len(frame) + 2, 2], "line": {"color": "#C69214", "width": 1.5}})
        chart.add_series({"name": "95% upper bound", "categories": ["Forecast", 3, 0, len(frame) + 2, 0], "values": ["Forecast", 3, 3, len(frame) + 2, 3], "line": {"color": "#C69214", "width": 1.5}})
        chart.set_title({"name": f"{horizon_days}-Day Price Forecast"})
        chart.set_y_axis({"name": "USD", "num_format": "$#,##0"})
        chart.set_legend({"position": "bottom"})
        sheet.insert_chart("F3", chart, {"x_scale": 1.5, "y_scale": 1.35})
    return output.getvalue()
