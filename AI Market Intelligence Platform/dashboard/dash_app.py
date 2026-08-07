from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make the project root importable regardless of the launch directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from dash import Dash, Input, Output, State, dcc, dash_table, html, no_update

from app.core.config import settings
from app.services.reporting import build_analysis_excel_report, build_forecast_excel_report

PALETTE = ["#1565C0", "#D32F2F", "#2E7D32", "#C69214", "#6A1B9A"]
DEFAULT_COIN = settings.tracked_coins[0]

API_URL = os.getenv("MARKET_API_URL", "http://127.0.0.1:8000/api").rstrip("/")
_HTTP = requests.Session()
_HTTP.trust_env = False


def api_get(path: str, **params) -> dict | list:
    response = _HTTP.get(f"{API_URL}{path}", params=params, timeout=60)
    response.raise_for_status()
    return response.json()


def refresh_market() -> dict:
    response = _HTTP.post(f"{API_URL}/market/refresh", timeout=60)
    response.raise_for_status()
    return response.json()


def price_format(value: float) -> str:
    return f"${value:,.2f}" if value >= 1 else f"${value:,.4f}"


def metric_card(label: str, value: str, sub: str = "") -> html.Div:
    return html.Div(
        [
            html.Div(label, style={"font-size": ".85rem", "color": "#5A6B82", "font-weight": 600}),
            html.Div(value, style={"font-size": "1.25rem", "font-weight": 700}),
            html.Div(sub, style={"font-size": ".8rem", "color": "#5A6B82"}),
        ],
        style={
            "border-left": "4px solid #1565C0", "padding": ".7rem 1rem", "min-width": "140px",
            "box-shadow": "0 1px 2px rgba(18,42,90,.06), 0 6px 18px rgba(18,42,90,.07)",
            "border-radius": "12px", "background": "#FFFFFF",
        },
    )


def _empty_figure(height: int = 350) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=20, b=10))
    return fig


app = Dash(__name__, title="AI Market Intelligence Platform")

app.layout = html.Div(
    style={"font-family": "Segoe UI, Arial, sans-serif", "margin": "0 auto", "max-width": "1440px", "padding": "1.4rem"},
    children=[
        dcc.Store(id="data-store", data={}),
        dcc.Store(id="refresh-signal", data=None),
        dcc.Interval(id="refresh-interval", interval=5 * 60 * 1000, n_intervals=0),
        dcc.Download(id="download-analysis"),
        dcc.Download(id="download-forecast"),
        html.H1("AI Market Intelligence Platform", style={"margin-bottom": "0"}),
        html.P(
            "Free crypto monitoring, technical analysis and transparent baseline forecasting.",
            style={"color": "#5A6B82", "margin-top": ".15rem"},
        ),
        html.Div(
            [
                html.Button("Refresh market data", id="refresh-button", n_clicks=0,
                            style={"border": "1px solid #E1E8F2", "border-radius": "10px", "padding": ".5rem 1rem", "font-weight": 600}),
                html.Span(id="refresh-status", style={"margin-left": "1rem", "color": "#5A6B82"}),
            ],
            style={"margin": ".75rem 0"},
        ),
        html.Div(id="coin-metrics", style={"display": "flex", "flex-wrap": "wrap", "gap": "1rem", "margin": "1rem 0"}),
        html.Div(
            style={"display": "flex", "gap": "1rem", "flex-wrap": "wrap", "margin": "1rem 0"},
            children=[
                html.Div(style={"flex": "2", "min-width": "260px"}, children=[
                    html.Label("Compare cryptocurrencies", style={"font-weight": 600}),
                    dcc.Dropdown(id="compare-select", multi=True, placeholder="All coins by default"),
                ]),
                html.Div(style={"flex": "1", "min-width": "200px"}, children=[
                    html.Label("Detailed analysis", style={"font-weight": 600}),
                    dcc.Dropdown(id="coin-detail", value=DEFAULT_COIN),
                ]),
                html.Div(style={"flex": "1", "min-width": "200px"}, children=[
                    html.Label("Analysis period", style={"font-weight": 600}),
                    dcc.Dropdown(
                        id="period-select", value=365,
                        options=[{"label": f"Last {d} day(s)", "value": d} for d in (1, 7, 30, 90, 365)],
                    ),
                    html.Small("CoinGecko's free API caps historical data at 365 days.",
                               style={"color": "#5A6B82"}),
                ]),
            ],
        ),
        html.Div(style={"display": "flex", "gap": "1.5rem", "flex-wrap": "wrap"}, children=[
            html.Div(style={"flex": "1", "min-width": "420px"}, children=[
                html.H3("Price history & moving averages"),
                dcc.Graph(id="price-chart"),
            ]),
            html.Div(style={"flex": "1", "min-width": "420px"}, children=[
                html.H3("Candlestick & trading volume"),
                dcc.Graph(id="candle-chart"),
            ]),
        ]),
        html.Div(style={"display": "flex", "gap": "1.5rem", "flex-wrap": "wrap"}, children=[
            html.Div(style={"flex": "1", "min-width": "420px"}, children=[
                html.H3("Relative performance comparison"),
                dcc.Graph(id="compare-chart"),
                html.Div(id="no-snapshots-note"),
            ]),
            html.Div(style={"flex": "1", "min-width": "420px"}, children=[
                html.H3("RSI, model forecast & 95% interval"),
                dcc.Graph(id="forecast-chart"),
                html.P(
                    "A flat point forecast is expected, not a bug: prices behave close to a random walk, so the best single estimate is \"around today's price\". The widening 95% band shows the growing uncertainty.",
                    style={"color": "#5A6B82", "font-size": ".85rem"},
                ),
            ]),
        ]),
        html.Div(style={"display": "flex", "gap": "1.5rem", "flex-wrap": "wrap"}, children=[
            html.Div(style={"flex": "1", "min-width": "420px"}, children=[
                html.H3("Market assistant"),
                html.Div(id="assistant-box"),
                html.Div([
                    html.Button("Download detailed analysis (.xlsx)", id="download-analysis-button", n_clicks=0,
                                style={"border": "1px solid #E1E8F2", "border-radius": "10px", "padding": ".5rem 1rem", "font-weight": 600, "margin-top": ".75rem"}),
                    html.Div([
                        html.Label("Forecast period", style={"font-weight": 600, "display": "block", "margin-top": ".75rem"}),
                        dcc.Dropdown(
                            id="forecast-horizon", value=90,
                            options=[{"label": key, "value": value} for key, value in
                                     {"1 month": 30, "3 months": 90, "6 months": 180, "1 year": 365, "3 years": 1095}.items()],
                        ),
                        html.Button("Generate & download forecast (.xlsx)", id="forecast-button", n_clicks=0,
                                    style={"border": "1px solid #E1E8F2", "border-radius": "10px", "padding": ".5rem 1rem", "font-weight": 600, "margin-top": ".5rem"}),
                    ]),
                    html.Small(
                        "Horizons beyond 90 days use an ARIMA baseline (recursive forecasts compound errors); 95% intervals widen with the horizon to reflect accumulating uncertainty.",
                        style={"color": "#5A6B82", "display": "block", "margin-top": ".5rem"},
                    ),
                ]),
            ]),
            html.Div(style={"flex": "1", "min-width": "420px"}, children=[
                html.H3("Alerts & data quality"),
                html.Div(id="alerts-box"),
                html.Div(id="quality-box", style={"margin-top": ".75rem", "color": "#5A6B82"}),
                html.Small(
                    "Source: CoinGecko public market data. Historical analysis is retrieved on demand; local snapshots are retained in SQLite.",
                    style={"color": "#5A6B82", "display": "block", "margin-top": ".75rem"},
                ),
            ]),
        ]),
        html.Hr(style={"border-color": "#E1E8F2", "margin": "1.5rem 0"}),
        html.Div(style={"display": "flex", "gap": "1.5rem", "flex-wrap": "wrap"}, children=[
            html.Div(style={"flex": "1", "min-width": "420px"}, children=[
                html.H3("Model evaluation · rolling time-series backtest"),
                html.Div(id="model-table"),
                html.P(
                    "Models are evaluated only on future folds, never with a random split, to reduce time-series leakage. The persistence (naive) baseline is \"predict the last price\" — models should beat it.",
                    style={"color": "#5A6B82", "font-size": ".85rem"},
                ),
                html.H3("Feature importance · what drives the forecast"),
                dcc.Graph(id="importance-chart"),
                html.Small(
                    "Gain-based importances from an XGBoost model fit on the full training window. Every analysis run is logged to MLflow — run `mlflow ui` in the project folder to explore runs — and recorded in logs/model_experiments.jsonl.",
                    style={"color": "#5A6B82"},
                ),
            ]),
            html.Div(style={"flex": "1", "min-width": "420px"}, children=[
                html.H3("Signal backtest · model vs buy & hold"),
                dcc.Graph(id="signals-chart"),
                html.Small(
                    "BUY/HOLD labels come from the XGBoost forecast for the next period; returns are the realized next-day returns of the selected analysis period.",
                    style={"color": "#5A6B82"},
                ),
            ]),
        ]),
    ],
)


@app.callback(
    Output("data-store", "data"),
    Input("refresh-interval", "n_intervals"),
    Input("refresh-signal", "data"),
    Input("coin-detail", "value"),
    Input("period-select", "value"),
)
def load_data(n_intervals: int, refresh_signal, coin_id: str, period: int) -> dict:
    coin_id = coin_id or DEFAULT_COIN
    period = period or 365
    store = {"snapshots": [], "snapshots_error": None, "analysis": None, "analysis_error": None,
             "summary": "", "alerts": [], "alerts_error": None}
    try:
        store["snapshots"] = api_get("/market/snapshots", limit=500)
    except requests.RequestException as exc:
        store["snapshots_error"] = str(exc)
    try:
        store["analysis"] = api_get(f"/market/analysis/{coin_id}", days=period)
    except requests.RequestException as exc:
        store["analysis_error"] = str(exc)
    try:
        store["summary"] = api_get("/assistant/summary", coin_id=coin_id)["summary"]
    except requests.RequestException:
        store["summary"] = "Refresh current market data to generate a local summary."
    try:
        store["alerts"] = api_get("/alerts", limit=5)
    except requests.RequestException as exc:
        store["alerts_error"] = str(exc)
    return store


@app.callback(
    Output("refresh-signal", "data"),
    Output("refresh-status", "children"),
    Input("refresh-button", "n_clicks"),
    prevent_initial_call=True,
)
def do_refresh(n_clicks: int):
    if not n_clicks:
        return None, ""
    try:
        result = refresh_market()
        return {"refreshed_at": datetime.now(timezone.utc).isoformat()}, \
            html.Span(f"Saved {result['saved']} new snapshots.", style={"color": "#2E7D32"})
    except Exception as exc:
        return None, html.Span(f"Refresh failed: {exc}", style={"color": "#D32F2F"})


@app.callback(
    Output("coin-detail", "options"),
    Output("compare-select", "options"),
    Output("coin-metrics", "children"),
    Output("compare-chart", "figure"),
    Output("no-snapshots-note", "children"),
    Input("data-store", "data"),
    Input("compare-select", "value"),
)
def update_controls_and_metrics(store: dict, compare_value):
    store = store or {}
    snapshots = store.get("snapshots") or []
    fallback_options = [{"label": coin.replace("-", " ").title(), "value": coin} for coin in settings.tracked_coins]
    if not snapshots:
        note = html.Div(
            "No local snapshots yet. Click “Refresh market data” to begin collecting the tracked coins.",
            style={"color": "#5A6B82", "margin": ".5rem 0"},
        )
        return fallback_options, fallback_options, [], _empty_figure(350), note

    frame = pd.DataFrame(snapshots)
    frame["captured_at"] = pd.to_datetime(frame["captured_at"], utc=True)
    latest = frame.sort_values("captured_at", ascending=False).drop_duplicates("coin_id")
    coin_labels = {row.coin_id: f"{row.name} ({row.symbol.upper()})" for _, row in latest.iterrows()}
    options = [{"label": label, "value": coin} for coin, label in coin_labels.items()]

    selected = compare_value or list(coin_labels)
    latest_selected = latest[latest["coin_id"].isin(selected)]
    cards = []
    for _, row in latest_selected.iterrows():
        change = float(row["change_24h_percent"] or 0)
        cards.append(metric_card(row["name"], price_format(float(row["price_usd"])), f"{change:+.2f}% · 24h"))

    compare_fig = _empty_figure(350)
    compare = frame[frame["coin_id"].isin(selected)].sort_values("captured_at").copy()
    if not compare.empty:
        compare["indexed_price"] = compare.groupby("coin_id")["price_usd"].transform(
            lambda values: values / values.iloc[0] * 100
        )
        for coin, group in compare.groupby("coin_id"):
            compare_fig.add_trace(go.Scatter(
                x=group["captured_at"], y=group["indexed_price"], mode="lines", name=coin_labels[coin],
            ))
        compare_fig.update_layout(
            height=350, margin=dict(l=10, r=10, t=20, b=10), legend=dict(orientation="h"),
            yaxis_title="Indexed price (first snapshot = 100)",
        )
    return options, options, cards, compare_fig, html.Div()


@app.callback(
    Output("price-chart", "figure"),
    Output("candle-chart", "figure"),
    Output("forecast-chart", "figure"),
    Input("data-store", "data"),
)
def update_charts(store: dict):
    store = store or {}
    analysis = store.get("analysis")
    empty = _empty_figure(380)
    if not analysis:
        return empty, empty, empty

    series = pd.DataFrame(analysis["series"])
    series["timestamp"] = pd.to_datetime(series["timestamp"])
    candles = pd.DataFrame(analysis["candles"])
    forecast = pd.DataFrame(analysis["forecast"])
    forecast["timestamp"] = pd.to_datetime(forecast["timestamp"])

    price_fig = go.Figure()
    price_fig.add_trace(go.Scatter(x=series["timestamp"], y=series["price_usd"], name="Price",
                                   line=dict(color=PALETTE[0], width=3)))
    price_fig.add_trace(go.Scatter(x=series["timestamp"], y=series["sma_7"], name="SMA 7",
                                   line=dict(color=PALETTE[3], width=2)))
    price_fig.add_trace(go.Scatter(x=series["timestamp"], y=series["sma_30"], name="SMA 30",
                                   line=dict(color=PALETTE[4], width=2)))
    price_fig.add_trace(go.Scatter(x=series["timestamp"], y=series["bollinger_upper"], name="Bollinger upper",
                                   line=dict(color=PALETTE[1], width=1, dash="dot")))
    price_fig.add_trace(go.Scatter(x=series["timestamp"], y=series["bollinger_lower"], name="Bollinger lower",
                                   line=dict(color=PALETTE[1], width=1, dash="dot"),
                                   fill="tonexty", fillcolor="rgba(211,47,47,.08)"))
    price_fig.update_layout(height=380, yaxis_title="USD", margin=dict(l=10, r=10, t=20, b=10),
                            legend=dict(orientation="h"))

    candle_fig = go.Figure()
    candle_fig.add_trace(go.Candlestick(
        x=candles["date"], open=candles["open"], high=candles["high"], low=candles["low"],
        close=candles["close"], name="OHLC", increasing_line_color=PALETTE[2], decreasing_line_color=PALETTE[1],
    ))
    candle_fig.add_trace(go.Bar(x=candles["date"], y=candles["volume_usd"], name="Volume",
                                marker_color="rgba(106,27,154,.35)", yaxis="y2"))
    candle_fig.update_layout(height=380, yaxis_title="USD",
                             yaxis2=dict(title="Volume", overlaying="y", side="right", showgrid=False),
                             margin=dict(l=10, r=10, t=20, b=10), legend=dict(orientation="h"),
                             xaxis_rangeslider_visible=False)

    forecast_fig = go.Figure()
    forecast_fig.add_trace(go.Scatter(x=series["timestamp"], y=series["price_usd"], name="Actual",
                                      line=dict(color=PALETTE[0], width=3)))
    forecast_fig.add_trace(go.Scatter(x=forecast["timestamp"], y=forecast["upper_95"], name="95% upper",
                                      line=dict(color="rgba(106,27,154,.35)", width=1), showlegend=False))
    forecast_fig.add_trace(go.Scatter(x=forecast["timestamp"], y=forecast["lower_95"],
                                      name="95% prediction interval",
                                      line=dict(color="rgba(106,27,154,.35)", width=1),
                                      fill="tonexty", fillcolor="rgba(106,27,154,.13)"))
    forecast_fig.add_trace(go.Scatter(x=forecast["timestamp"], y=forecast["price_usd"],
                                      name=f"{analysis['metrics']['selected_model']} forecast",
                                      line=dict(color=PALETTE[4], width=3, dash="dash")))
    forecast_fig.add_trace(go.Scatter(x=series["timestamp"], y=series["rsi_14"], name="RSI 14",
                                      line=dict(color=PALETTE[3]), yaxis="y2"))
    forecast_fig.add_hline(y=70, line_color=PALETTE[1], line_dash="dot", yref="y2")
    forecast_fig.add_hline(y=30, line_color=PALETTE[2], line_dash="dot", yref="y2")
    forecast_fig.update_layout(height=350, yaxis_title="USD",
                               yaxis2=dict(title="RSI", range=[0, 100], overlaying="y", side="right"),
                               margin=dict(l=10, r=10, t=20, b=10), legend=dict(orientation="h"))

    return price_fig, candle_fig, forecast_fig


@app.callback(
    Output("model-table", "children"),
    Output("importance-chart", "figure"),
    Output("signals-chart", "figure"),
    Input("data-store", "data"),
)
def update_evaluation(store: dict):
    store = store or {}
    analysis = store.get("analysis")
    empty = _empty_figure(300)
    if not analysis:
        return html.Div("Choose 90 or 365 days to collect enough observations for rolling model evaluation.",
                        style={"color": "#5A6B82"}), empty, empty

    comparison = analysis.get("model_comparison") or []
    if comparison:
        table = dash_table.DataTable(
            columns=[
                {"name": "Model", "id": "model"}, {"name": "MAE", "id": "mae"},
                {"name": "RMSE", "id": "rmse"}, {"name": "Folds", "id": "folds"},
            ],
            data=comparison,
            style_cell={"textAlign": "left"},
            style_table={"overflowX": "auto"},
        )
    else:
        table = html.Div("Choose 90 or 365 days to collect enough observations for rolling model evaluation.",
                         style={"color": "#5A6B82"})

    importance_fig = empty
    importance = analysis.get("feature_importance") or []
    if importance:
        importance_frame = pd.DataFrame(importance)
        importance_fig = px.bar(
            importance_frame, x="importance", y="feature", orientation="h",
            color="importance", color_continuous_scale="Blues",
            labels={"importance": "Gain importance", "feature": "Feature"},
        )
        importance_fig.update_layout(height=300, margin=dict(l=10, r=10, t=20, b=10),
                                     yaxis=dict(autorange="reversed"), coloraxis_showscale=False)

    signals_fig = empty
    signals = analysis.get("signals") or []
    if signals:
        signals_frame = pd.DataFrame(signals)
        signals_frame["timestamp"] = pd.to_datetime(signals_frame["timestamp"])
        signals_fig = px.bar(
            signals_frame, x="timestamp", y="actual_return", color="signal",
            color_discrete_map={"BUY": PALETTE[2], "HOLD": PALETTE[3]},
            labels={"actual_return": "Next-period return", "timestamp": "Time"},
        )
        signals_fig.update_layout(height=260, margin=dict(l=10, r=10, t=20, b=10), legend=dict(orientation="h"))

    return table, importance_fig, signals_fig


@app.callback(
    Output("assistant-box", "children"),
    Output("alerts-box", "children"),
    Output("quality-box", "children"),
    Input("data-store", "data"),
)
def update_info(store: dict):
    store = store or {}
    analysis = store.get("analysis")
    if not analysis:
        note = store.get("analysis_error") or "Loading analysis…"
        return (html.Div(f"Historical analysis is temporarily unavailable: {note}", style={"color": "#D32F2F"}),
                html.Div(), html.Div())

    metrics = analysis["metrics"]
    summary = store.get("summary") or ""
    assistant = [
        html.P(summary, style={"font-size": ".95rem"}),
        html.Div(style={"display": "flex", "gap": "1rem", "flex-wrap": "wrap"}, children=[
            metric_card("Trend", metrics["trend"].title()),
            metric_card("RSI (14)", f"{metrics['rsi_14']:.1f}", metrics["rsi_state"]),
            metric_card("Volatility", f"{metrics['volatility_percent']:.2f}%"),
            metric_card("Fear & Greed", f"{metrics['fear_greed']:.0f}"),
        ]),
        html.P(
            f"VWAP: {price_format(metrics['vwap'])} · Bollinger: {metrics['bollinger_state']} · "
            f"ADF p-value after differencing: {metrics['adf_pvalue'] if metrics['adf_pvalue'] is not None else 'N/A'}",
            style={"color": "#5A6B82", "font-size": ".85rem"},
        ),
    ]

    alerts = store.get("alerts") or []
    if alerts:
        alert_children = [
            html.Div(f"{alert['severity'].upper()}: {alert['message']}",
                     style={"background": "#FFF4E5", "border-radius": "10px", "padding": ".5rem .75rem",
                            "margin": ".25rem 0"})
            for alert in alerts[:3]
        ]
    else:
        alert_children = [html.Div("No significant ±5% movement alerts are currently recorded.",
                                   style={"color": "#2E7D32"})]
    if store.get("alerts_error"):
        alert_children.append(html.Div(f"Alerts unavailable: {store['alerts_error']}", style={"color": "#D32F2F"}))

    snapshots = store.get("snapshots") or []
    if snapshots:
        frame = pd.DataFrame(snapshots)
        newest = pd.to_datetime(frame["captured_at"], utc=True).max().to_pydatetime()
        age_minutes = (datetime.now(timezone.utc) - newest).total_seconds() / 60
        quality_children = [
            html.Div([html.Span("Stored snapshots: "), html.Strong(f"{len(frame):,}")]),
            html.Div([html.Span("Tracked coins: "), html.Strong(f"{frame['coin_id'].nunique()}")]),
            html.Div([html.Span("Last refresh: "), html.Strong(f"{age_minutes:.0f} min ago")]),
        ]
    else:
        quality_children = [html.Div("No data yet — click Refresh market data.")]

    return assistant, alert_children, quality_children


@app.callback(
    Output("download-analysis", "data"),
    Input("download-analysis-button", "n_clicks"),
    State("data-store", "data"),
    State("coin-detail", "value"),
    State("period-select", "value"),
    prevent_initial_call=True,
)
def download_analysis(n_clicks: int, store: dict, coin_id: str, period: int):
    store = store or {}
    analysis = store.get("analysis")
    if not analysis:
        return no_update
    snapshots = store.get("snapshots") or []
    label = next((f"{row['name']} ({row['symbol'].upper()})" for row in snapshots if row["coin_id"] == coin_id),
                 coin_id or DEFAULT_COIN)
    report_bytes = build_analysis_excel_report(label, coin_id, analysis, store.get("summary") or "", days=period)
    return dcc.send_bytes(report_bytes, f"{coin_id}_{period}_day_market_analysis.xlsx")


@app.callback(
    Output("download-forecast", "data"),
    Input("forecast-button", "n_clicks"),
    State("data-store", "data"),
    State("coin-detail", "value"),
    State("period-select", "value"),
    State("forecast-horizon", "value"),
    prevent_initial_call=True,
)
def download_forecast(n_clicks: int, store: dict, coin_id: str, period: int, horizon: int):
    coin_id = coin_id or DEFAULT_COIN
    period = period or 365
    if not horizon:
        return no_update
    try:
        forecast_analysis = api_get(f"/market/analysis/{coin_id}", days=period, forecast_days=horizon)
    except requests.RequestException:
        return no_update
    snapshots = (store or {}).get("snapshots") or []
    label = next((f"{row['name']} ({row['symbol'].upper()})" for row in snapshots if row["coin_id"] == coin_id),
                 coin_id)
    report_bytes = build_forecast_excel_report(
        label, coin_id, forecast_analysis["forecast"],
        forecast_analysis["metrics"]["forecast_method"], horizon,
    )
    return dcc.send_bytes(report_bytes, f"{coin_id}_{horizon}_day_forecast.xlsx")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8501, debug=False)
