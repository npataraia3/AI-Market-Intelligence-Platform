from __future__ import annotations

import os
from datetime import datetime, timezone

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import requests
import streamlit as st

from app.services.reporting import build_analysis_excel_report, build_forecast_excel_report

PALETTE = ["#1565C0", "#D32F2F", "#2E7D32", "#C69214", "#6A1B9A"]


def _api_url() -> str:
    configured = os.getenv("MARKET_API_URL")
    if configured:
        return configured.rstrip("/")
    try:
        return st.secrets.get("api_url", "http://127.0.0.1:8000/api").rstrip("/")
    except Exception:
        return "http://127.0.0.1:8000/api"


API_URL = _api_url()

st.set_page_config(page_title="AI Market Intelligence", page_icon="📈", layout="wide")

THEME_BASE = st.get_option("theme.base")
pio.templates.default = "plotly_dark" if THEME_BASE == "dark" else "plotly_white"

st.markdown(
    """<style>
    :root {
        --bg: #F4F7FB;
        --surface: #FFFFFF;
        --border: #E1E8F2;
        --text: #17202E;
        --text-muted: #5A6B82;
        --primary: #1565C0;
        --primary-2: #6A1B9A;
        --accent: #C69214;
        --shadow: 0 1px 2px rgba(18, 42, 90, .06), 0 6px 18px rgba(18, 42, 90, .07);
        --radius: 14px;
    }
    @media (prefers-color-scheme: dark) {
        :root {
            --bg: #0B1220;
            --surface: #131C2E;
            --border: #26324B;
            --text: #E7EDF7;
            --text-muted: #93A6C2;
            --shadow: 0 1px 2px rgba(0, 0, 0, .5), 0 8px 22px rgba(0, 0, 0, .45);
        }
    }
    .stApp { background: var(--bg); }
    .stMainBlockContainer { max-width: 1440px; padding-top: 1.4rem; margin: 0 auto; }

    .dashboard-title {
        font-size: 2rem; font-weight: 800; letter-spacing: -.6px; margin: 0;
        background: linear-gradient(90deg, var(--primary), var(--primary-2));
        -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
    }
    .dashboard-subtitle { color: var(--text-muted); margin: .15rem 0 0; font-size: .98rem; }
    .section-label {
        color: var(--primary-2); font-weight: 700; letter-spacing: .4px;
        text-transform: uppercase; font-size: .78rem; margin: .2rem 0;
    }
    h2, h3 { color: var(--text); letter-spacing: -.2px; }
    .stCaption, [data-testid="stCaptionContainer"] p { color: var(--text-muted); }

    [data-testid="stMetric"] {
        background: var(--surface); border: 1px solid var(--border);
        border-left: 4px solid var(--primary); border-radius: var(--radius);
        padding: .9rem 1rem; box-shadow: var(--shadow);
    }
    [data-testid="stMetricLabel"] { color: var(--text-muted); font-size: .85rem; font-weight: 600; }
    [data-testid="stMetricValue"] { color: var(--text); font-weight: 700; }
    [data-testid="stMetricDelta"] { color: var(--text-muted); }

    .stButton > button, .stDownloadButton > button {
        border-radius: 10px; font-weight: 600; border: 1px solid var(--border);
        transition: transform .12s ease, box-shadow .12s ease;
    }
    .stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {
        background: linear-gradient(90deg, var(--primary), var(--primary-2));
        border: none; color: #FFFFFF;
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        transform: translateY(-1px); box-shadow: var(--shadow);
    }

    [data-testid="stDataFrame"] { border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; }
    div[data-testid="stAlert"] { border-radius: var(--radius); }
    hr { border-color: var(--border); }
    </style>""",
    unsafe_allow_html=True,
)


_HTTP = requests.Session()
_HTTP.trust_env = False


def api_get(path: str, **params):
    response = _HTTP.get(f"{API_URL}{path}", params=params, timeout=35)
    response.raise_for_status()
    return response.json()


def refresh_market() -> dict:
    response = _HTTP.post(f"{API_URL}/market/refresh", timeout=35)
    response.raise_for_status()
    return response.json()


def price_format(value: float) -> str:
    return f"${value:,.2f}" if value >= 1 else f"${value:,.4f}"


st.markdown('<h1 class="dashboard-title">AI Market Intelligence Platform</h1>', unsafe_allow_html=True)
st.markdown('<p class="dashboard-subtitle">Free crypto monitoring, technical analysis and transparent baseline forecasting.</p>', unsafe_allow_html=True)

try:
    snapshots = api_get("/market/snapshots", limit=500)
except requests.RequestException:
    snapshots = []

left, right = st.columns([1, 2], vertical_alignment="bottom")
with left:
    if st.button("↻ Refresh market data", type="primary", width="stretch"):
        try:
            result = refresh_market()
            st.success(f"Saved {result['saved']} new snapshots.")
            st.rerun()
        except requests.RequestException as exc:
            st.error(f"Refresh failed: {exc}")
with right:
    st.caption("Refresh saves a local snapshot and checks the configurable ±5% movement alert threshold.")

if not snapshots:
    st.info("No local snapshots yet. Click “Refresh market data” to begin collecting the tracked coins.")
    st.stop()

snapshots_frame = pd.DataFrame(snapshots)
snapshots_frame["captured_at"] = pd.to_datetime(snapshots_frame["captured_at"], utc=True)
latest = snapshots_frame.sort_values("captured_at", ascending=False).drop_duplicates("coin_id")
coin_labels = {row.coin_id: f"{row.name} ({row.symbol.upper()})" for _, row in latest.iterrows()}

control_a, control_b, control_c = st.columns([2, 1, 1])
with control_a:
    selected_coins = st.multiselect(
        "Compare cryptocurrencies", list(coin_labels), default=list(coin_labels),
        format_func=lambda coin: coin_labels[coin],
    )
with control_b:
    selected_coin = st.selectbox("Detailed analysis", list(coin_labels), format_func=lambda coin: coin_labels[coin])
with control_c:
    period = st.selectbox("Analysis period", [1, 7, 30, 90, 365], index=4, format_func=lambda days: f"Last {days} day(s)")
    st.caption("CoinGecko's free API caps historical data at 365 days.")

selected_latest = latest[latest["coin_id"].isin(selected_coins)]
metric_columns = st.columns(max(1, len(selected_latest)))
for column, (_, row) in zip(metric_columns, selected_latest.iterrows()):
    change = float(row["change_24h_percent"] or 0)
    column.metric(row["name"], price_format(float(row["price_usd"])), f"{change:+.2f}% · 24h")

try:
    analysis = api_get(f"/market/analysis/{selected_coin}", days=period)
except requests.RequestException as exc:
    st.error(f"Historical analysis is temporarily unavailable: {exc}")
    analysis = None

chart_left, chart_right = st.columns(2)
with chart_left:
    st.subheader("Price history & moving averages")
    if analysis:
        series = pd.DataFrame(analysis["series"])
        series["timestamp"] = pd.to_datetime(series["timestamp"])
        price_fig = go.Figure()
        price_fig.add_trace(go.Scatter(x=series["timestamp"], y=series["price_usd"], name="Price", line=dict(color=PALETTE[0], width=3)))
        price_fig.add_trace(go.Scatter(x=series["timestamp"], y=series["sma_7"], name="SMA 7", line=dict(color=PALETTE[3], width=2)))
        price_fig.add_trace(go.Scatter(x=series["timestamp"], y=series["sma_30"], name="SMA 30", line=dict(color=PALETTE[4], width=2)))
        price_fig.add_trace(go.Scatter(x=series["timestamp"], y=series["bollinger_upper"], name="Bollinger upper", line=dict(color=PALETTE[1], width=1, dash="dot")))
        price_fig.add_trace(go.Scatter(x=series["timestamp"], y=series["bollinger_lower"], name="Bollinger lower", line=dict(color=PALETTE[1], width=1, dash="dot"), fill="tonexty", fillcolor="rgba(211,47,47,.08)"))
        price_fig.update_layout(height=380, yaxis_title="USD", margin=dict(l=10, r=10, t=20, b=10), legend=dict(orientation="h"))
        st.plotly_chart(price_fig, width="stretch")

with chart_right:
    st.subheader("Candlestick & trading volume")
    if analysis:
        candles = pd.DataFrame(analysis["candles"])
        candle_fig = go.Figure()
        candle_fig.add_trace(go.Candlestick(x=candles["date"], open=candles["open"], high=candles["high"], low=candles["low"], close=candles["close"], name="OHLC", increasing_line_color=PALETTE[2], decreasing_line_color=PALETTE[1]))
        candle_fig.add_trace(go.Bar(x=candles["date"], y=candles["volume_usd"], name="Volume", marker_color="rgba(106,27,154,.35)", yaxis="y2"))
        candle_fig.update_layout(height=380, yaxis_title="USD", yaxis2=dict(title="Volume", overlaying="y", side="right", showgrid=False), margin=dict(l=10, r=10, t=20, b=10), legend=dict(orientation="h"), xaxis_rangeslider_visible=False)
        st.plotly_chart(candle_fig, width="stretch")

comparison_left, comparison_right = st.columns(2)
with comparison_left:
    st.subheader("Relative performance comparison")
    compare = snapshots_frame[snapshots_frame["coin_id"].isin(selected_coins)].sort_values("captured_at").copy()
    if compare.empty:
        st.info("Select at least one cryptocurrency to compare.")
    else:
        compare["indexed_price"] = compare.groupby("coin_id")["price_usd"].transform(lambda values: values / values.iloc[0] * 100)
        compare_fig = px.line(compare, x="captured_at", y="indexed_price", color="name", color_discrete_sequence=PALETTE, labels={"indexed_price": "Indexed price (first snapshot = 100)", "captured_at": "Captured time"})
        compare_fig.update_layout(height=350, margin=dict(l=10, r=10, t=20, b=10), legend=dict(orientation="h"))
        st.plotly_chart(compare_fig, width="stretch")

with comparison_right:
    st.subheader("RSI, model forecast & 95% interval")
    if analysis:
        series = pd.DataFrame(analysis["series"])
        forecast = pd.DataFrame(analysis["forecast"])
        series["timestamp"] = pd.to_datetime(series["timestamp"])
        forecast["timestamp"] = pd.to_datetime(forecast["timestamp"])
        forecast_fig = go.Figure()
        forecast_fig.add_trace(go.Scatter(x=series["timestamp"], y=series["price_usd"], name="Actual", line=dict(color=PALETTE[0], width=3)))
        forecast_fig.add_trace(go.Scatter(x=forecast["timestamp"], y=forecast["upper_95"], name="95% upper", line=dict(color="rgba(106,27,154,.35)", width=1), showlegend=False))
        forecast_fig.add_trace(go.Scatter(x=forecast["timestamp"], y=forecast["lower_95"], name="95% prediction interval", line=dict(color="rgba(106,27,154,.35)", width=1), fill="tonexty", fillcolor="rgba(106,27,154,.13)"))
        forecast_fig.add_trace(go.Scatter(x=forecast["timestamp"], y=forecast["price_usd"], name=f"{analysis['metrics']['selected_model']} forecast", line=dict(color=PALETTE[4], width=3, dash="dash")))
        forecast_fig.add_trace(go.Scatter(x=series["timestamp"], y=series["rsi_14"], name="RSI 14", line=dict(color=PALETTE[3]), yaxis="y2"))
        forecast_fig.add_hline(y=70, line_color=PALETTE[1], line_dash="dot", yref="y2")
        forecast_fig.add_hline(y=30, line_color=PALETTE[2], line_dash="dot", yref="y2")
        forecast_fig.update_layout(height=350, yaxis_title="USD", yaxis2=dict(title="RSI", range=[0, 100], overlaying="y", side="right"), margin=dict(l=10, r=10, t=20, b=10), legend=dict(orientation="h"))
        st.plotly_chart(forecast_fig, width="stretch")
        st.caption("A flat point forecast is expected, not a bug: prices behave close to a random walk, so the best single estimate is \"around today's price\". The widening 95% band shows the growing uncertainty — the further out, the wider the likely range.")

info_left, info_right = st.columns(2)
with info_left:
    st.subheader("Market assistant")
    if analysis:
        metrics = analysis["metrics"]
        try:
            summary = api_get("/assistant/summary", coin_id=selected_coin)["summary"]
        except requests.RequestException:
            summary = "Refresh current market data to generate a local summary."
        st.write(summary)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Trend", metrics["trend"].title())
        c2.metric("RSI (14)", f"{metrics['rsi_14']:.1f}", metrics["rsi_state"])
        c3.metric("Volatility", f"{metrics['volatility_percent']:.2f}%")
        c4.metric("Fear & Greed", f"{metrics['fear_greed']:.0f}")
        st.caption(f"VWAP: {price_format(metrics['vwap'])} · Bollinger: {metrics['bollinger_state']} · ADF p-value after differencing: {metrics['adf_pvalue'] if metrics['adf_pvalue'] is not None else 'N/A'}")
        report_bytes = build_analysis_excel_report(coin_labels[selected_coin], selected_coin, analysis, summary, days=period)
        st.download_button(
            f"Download detailed {period}-day analysis (.xlsx)",
            data=report_bytes,
            file_name=f"{selected_coin}_{period}_day_market_analysis.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
        st.caption("The Excel workbook always covers the analysis period selected above.")
        st.markdown('<p class="section-label">Forecast download</p>', unsafe_allow_html=True)
        forecast_options = {"1 month": 30, "3 months": 90, "6 months": 180, "1 year": 365, "3 years": 1095}
        horizon_label = st.selectbox("Forecast period", list(forecast_options), key="forecast_horizon")
        horizon_days = forecast_options[horizon_label]
        forecast_key = (selected_coin, period, horizon_days)
        if st.session_state.get("forecast_key") != forecast_key:
            st.session_state["forecast_key"] = forecast_key
            st.session_state["forecast_bytes"] = None
            st.session_state["forecast_file_name"] = None
        if st.button(f"Generate {horizon_label} forecast file", width="stretch"):
            try:
                forecast_analysis = api_get(f"/market/analysis/{selected_coin}", days=period, forecast_days=horizon_days)
                st.session_state["forecast_bytes"] = build_forecast_excel_report(
                    coin_labels[selected_coin], selected_coin, forecast_analysis["forecast"],
                    forecast_analysis["metrics"]["forecast_method"], horizon_days,
                )
                st.session_state["forecast_file_name"] = f"{selected_coin}_{horizon_days}_day_forecast.xlsx"
            except requests.RequestException as exc:
                st.error(f"Forecast generation failed: {exc}")
        if st.session_state.get("forecast_bytes"):
            st.download_button(
                f"Download {horizon_label} forecast (.xlsx)",
                data=st.session_state["forecast_bytes"],
                file_name=st.session_state["forecast_file_name"],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )
        st.caption("Horizons beyond 90 days use an ARIMA baseline (recursive forecasts compound errors), and 95% intervals widen with the horizon to reflect accumulating uncertainty.")

with info_right:
    st.subheader("Alerts & data quality")
    try:
        alerts = api_get("/alerts", limit=5)
    except requests.RequestException:
        alerts = []
    if alerts:
        for alert in alerts[:3]:
            st.warning(f"{alert['severity'].upper()}: {alert['message']}")
    else:
        st.success("No significant ±5% movement alerts are currently recorded.")
    newest = snapshots_frame["captured_at"].max().to_pydatetime()
    age_minutes = (datetime.now(timezone.utc) - newest).total_seconds() / 60
    d1, d2, d3 = st.columns(3)
    d1.metric("Stored snapshots", f"{len(snapshots_frame):,}")
    d2.metric("Tracked coins", latest["coin_id"].nunique())
    d3.metric("Last refresh", f"{age_minutes:.0f} min ago")
    st.caption("Source: CoinGecko public market data. Historical analysis is retrieved on demand; local snapshots are retained in SQLite.")

st.divider()
evaluation_left, evaluation_right = st.columns(2)
with evaluation_left:
    st.subheader("Model evaluation · rolling time-series backtest")
    if analysis and analysis["model_comparison"]:
        model_frame = pd.DataFrame(analysis["model_comparison"])
        st.dataframe(model_frame.style.format({"mae": "${:,.2f}", "rmse": "${:,.2f}"}), width="stretch", hide_index=True)
        st.caption("Models are evaluated only on future folds, never with a random split, to reduce time-series leakage. The persistence (naive) baseline is \"predict the last price\" — models should beat it.")
    else:
        st.info("Choose 90 or 365 days to collect enough observations for rolling model evaluation.")
    if analysis and analysis.get("feature_importance"):
        st.subheader("Feature importance · what drives the forecast")
        importance = pd.DataFrame(analysis["feature_importance"])
        importance_fig = px.bar(
            importance, x="importance", y="feature", orientation="h",
            color="importance", color_continuous_scale="Blues",
            labels={"importance": "Gain importance", "feature": "Feature"},
        )
        importance_fig.update_layout(height=300, margin=dict(l=10, r=10, t=20, b=10), yaxis=dict(autorange="reversed"), coloraxis_showscale=False)
        st.plotly_chart(importance_fig, width="stretch")
        st.caption("Gain-based importances from an XGBoost model fit on the full training window.")
    st.caption("Every analysis run is logged to MLflow — run `mlflow ui` in the project folder to explore runs — and recorded in `logs/model_experiments.jsonl`.")

with evaluation_right:
    st.subheader("Signal backtest · model vs buy & hold")
    if analysis:
        metrics = analysis["metrics"]
        b1, b2, b3 = st.columns(3)
        b1.metric("Selected model", metrics["selected_model"])
        b2.metric("Model signal return", f"{metrics['strategy_return_percent']:+.2f}%")
        b3.metric("Buy & hold return", f"{metrics['buy_hold_return_percent']:+.2f}%")
        signals = pd.DataFrame(analysis["signals"])
        if not signals.empty:
            signals["timestamp"] = pd.to_datetime(signals["timestamp"])
            signal_fig = px.bar(signals, x="timestamp", y="actual_return", color="signal", color_discrete_map={"BUY": PALETTE[2], "HOLD": PALETTE[3]}, labels={"actual_return": "Next-period return", "timestamp": "Time"})
            signal_fig.update_layout(height=260, margin=dict(l=10, r=10, t=20, b=10), legend=dict(orientation="h"))
            st.plotly_chart(signal_fig, width="stretch")
        else:
            st.caption("No backtest signals are available for the selected period.")
