"""Premium landing page for the AI Market Intelligence Platform.

The homepage is a full-bleed page (no sidebar shell) rendered at ``/``. It
combines a hero section with an abstract market visualization, a grid of
interactive feature cards that route to the real application sections, an
editorial section index and a minimal footer. Live values (BTC/ETH price,
sentiment, risk metrics, alerts) are injected by callbacks in ``dash_app.py``
from the shared ``data-store``; every element degrades gracefully to a
placeholder when the API is offline.
"""

from __future__ import annotations

from dash import dcc, html

# ---------------------------------------------------------------- helpers


def _svg(content: str, cls: str = "") -> dcc.Markdown:
    return dcc.Markdown(
        dangerously_allow_html=True,
        className=f"icon-svg {cls}",
        children=(f"<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.6' "
                  f"stroke-linecap='round' stroke-linejoin='round'>{content}</svg>"),
    )


def _logo_svg() -> str:
    # Abstract mark: an upward market pulse through a data node ring.
    return (
        "<svg viewBox='0 0 30 30' fill='none' xmlns='http://www.w3.org/2000/svg'>"
        "<circle cx='15' cy='15' r='12' stroke='#1F3B5B' stroke-width='1.2' opacity='.35'/>"
        "<circle cx='15' cy='15' r='7' stroke='#1F3B5B' stroke-width='1.2' opacity='.5'/>"
        "<circle cx='15' cy='15' r='3' fill='#3976D2'/>"
        "<path d='M4 22 L10 14 L13 18 L19 8 L24 12' stroke='#3976D2' stroke-width='1.8' "
        "stroke-linecap='round' stroke-linejoin='round'/>"
        "</svg>"
    )


def _sparkline_svg(points, width: int = 240, height: int = 64, stroke: str = "#3976D2",
                   fill: bool = True, area: str = "rgba(57,118,210,.12)") -> str:
    """Build a polyline sparkline SVG from a list of numeric points."""
    if not points:
        points = [50] * 12
    if len(points) == 1:
        points = points * 12
    lo, hi = min(points), max(points)
    span = (hi - lo) or 1.0
    step = width / (len(points) - 1)
    coords = []
    for i, value in enumerate(points):
        x = i * step
        y = height - 6 - (value - lo) / span * (height - 12)
        coords.append(f"{x:.1f},{y:.1f}")
    polyline = " ".join(coords)
    area_points = f"0,{height} {polyline} {width},{height}"
    fill_attr = f"<polygon points='{area_points}' fill='{area}'/>" if fill else ""
    return (f"<svg viewBox='0 0 {width} {height}' xmlns='http://www.w3.org/2000/svg' "
            f"preserveAspectRatio='none'>{fill_attr}"
            f"<polyline points='{polyline}' fill='none' stroke='{stroke}' stroke-width='2' "
            f"stroke-linecap='round' stroke-linejoin='round'/></svg>")


_ICONS = {
    "pulse": _svg("<path d='M2 12h4l3-7 5 14 3-7h5'/>"),
    "chart": _svg("<path d='M3 21h18'/><path d='M5 15l5-6 4 3 6-8'/>"),
    "forecast": _svg("<path d='M3 21h18'/><path d='M4 16c3-8 6-8 9-4s5-2 7-8'/>"
                     "<path d='M15 2l5 2-2 5'/>"),
    "risk": _svg("<path d='M12 3l8 5v8l-8 5-8-5V8z'/><path d='M12 8v4'/><circle cx='12' cy='15.5' r='.5' fill='currentColor'/>"),
    "gauge": _svg("<path d='M4 16a9 9 0 0 1 16 0'/><path d='M12 16l4-4'/>"
                  "<circle cx='12' cy='16' r='1.4' fill='currentColor'/>"),
    "bell": _svg("<path d='M6 17h12l-1.5-1.5V10a4.5 4.5 0 0 0-9 0v5.5z'/>"
                 "<path d='M10 20a2 2 0 0 0 4 0'/>"),
    "layers": _svg("<path d='M12 3l9 5-9 5-9-5z'/><path d='M3 13l9 5 9-5'/><path d='M3 18l9 5 9-5'/>"),
    "loop": _svg("<path d='M4 9a7 7 0 0 1 12-3l3 3'/><path d='M20 15a7 7 0 0 1-12 3l-3-3'/>"
                 "<path d='M19 3v6h-6'/><path d='M5 21v-6h6'/>"),
}


# ---------------------------------------------------------------- sections


def _nav_bar() -> html.Header:
    return html.Header(
        className="home-header",
        children=[
            html.A(
                href="/",
                className="home-brand",
                children=[
                    dcc.Markdown(dangerously_allow_html=True, className="home-logo", children=_logo_svg()),
                    html.Span("AI Market Intelligence", className="home-brand-name"),
                ],
            ),
            html.Nav(
                className="home-nav",
                children=[
                    dcc.Link("Overview", href="/overview", className="home-nav-item"),
                    dcc.Link("Market", href="/markets", className="home-nav-item"),
                    dcc.Link("Analysis", href="/forecast", className="home-nav-item"),
                    dcc.Link("Forecast", href="/forecast", className="home-nav-item"),
                    dcc.Link("Risk", href="/risk", className="home-nav-item"),
                    dcc.Link("Alerts", href="/alerts", className="home-nav-item"),
                ],
            ),
            html.Div(
                className="home-nav-right",
                children=[
                    dcc.Link("API", href="http://127.0.0.1:8000/api", className="home-nav-link"),
                    dcc.Link("Models", href="/strategy", className="home-nav-link"),
                ],
            ),
        ],
    )


def _hero() -> html.Section:
    return html.Section(
        className="home-hero",
        children=[
            html.Div(
                className="home-hero-copy",
                children=[
                    html.Div("Cryptocurrency market intelligence", className="home-eyebrow"),
                    html.H1(
                        className="home-title",
                        children=[
                            html.Span("TURN CRYPTO", className="home-title-line"),
                            html.Span("MARKET DATA", className="home-title-line home-title-accent"),
                            html.Span("INTO", className="home-title-line"),
                            html.Span("INTELLIGENT", className="home-title-line home-title-accent"),
                            html.Span("INSIGHTS.", className="home-title-line"),
                        ],
                    ),
                    html.P(
                        "Analyze real-time cryptocurrency market data, discover trends and "
                        "anomalies, evaluate forecasting models, monitor risk, and explore "
                        "transparent market intelligence — all locally, without a paid API or "
                        "cloud account.",
                        className="home-lead",
                    ),
                    html.Div(
                        className="home-cta",
                        children=[
                            dcc.Link("EXPLORE MARKET", href="/forecast",
                                     className="home-btn home-btn-primary"),
                            html.A("VIEW ALL FEATURES", href="#home-features",
                                   className="home-btn home-btn-ghost"),
                        ],
                    ),
                    html.Div(
                        className="home-hero-flow",
                        children=[
                            html.Span("DATA", className="home-flow-step"),
                            html.Span("→", className="home-flow-arrow"),
                            html.Span("ANALYSIS", className="home-flow-step"),
                            html.Span("→", className="home-flow-arrow"),
                            html.Span("INTELLIGENCE", className="home-flow-step"),
                            html.Span("→", className="home-flow-arrow"),
                            html.Span("DECISION SUPPORT", className="home-flow-step"),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="home-hero-visual",
                children=[
                    html.Div(className="hero-grid-bg"),
                    html.Div(className="hero-orbit"),
                    html.Div(
                        className="hero-card hero-card-btc",
                        children=[
                            html.Div(className="hero-card-tag", children=[
                                html.Span(className="hero-dot hero-dot-btc"),
                                html.Span("BTC"),
                            ]),
                            html.Div(id="home-hero-btc-price", className="hero-card-price", children="$67,421"),
                            html.Div(id="home-hero-btc-change", className="hero-card-change text-secondary", children="+2.43% / 24h"),
                        ],
                    ),
                    html.Div(
                        className="hero-card hero-card-eth",
                        children=[
                            html.Div(className="hero-card-tag", children=[
                                html.Span(className="hero-dot hero-dot-eth"),
                                html.Span("ETH"),
                            ]),
                            html.Div(id="home-hero-eth-price", className="hero-card-price", children="$3,421"),
                            html.Div(id="home-hero-eth-change", className="hero-card-change text-secondary", children="+1.70% / 24h"),
                        ],
                    ),
                    html.Div(
                        className="hero-card hero-card-sentiment",
                        children=[
                            html.Div("MARKET SENTIMENT", className="hero-card-label"),
                            html.Div(id="home-hero-sentiment-value", className="hero-sentiment-value", children="72"),
                            html.Div(id="home-hero-sentiment-label", className="hero-sentiment-label", children="GREED"),
                            html.Div(className="hero-gauge", children=[
                                html.Div(id="home-hero-gauge-fill", className="hero-gauge-fill", style={"width": "72%"}),
                            ]),
                        ],
                    ),
                    html.Div(
                        className="hero-card hero-card-spark",
                        children=[
                            html.Div("90-DAY RELATIVE PERFORMANCE", className="hero-card-label"),
                            dcc.Markdown(id="home-hero-spark", dangerously_allow_html=True,
                                         children=_sparkline_svg([])),
                        ],
                    ),
                    html.Div(
                        className="hero-card hero-card-vol",
                        children=[
                            html.Div("VOLATILITY", className="hero-card-label"),
                            html.Div(id="home-hero-volatility", className="hero-vol-value", children="42.8%"),
                            html.Div("30D ANNUALIZED", className="hero-card-label-sub"),
                        ],
                    ),
                    html.Div(className="hero-node hero-node-1"),
                    html.Div(className="hero-node hero-node-2"),
                    html.Div(className="hero-node hero-node-3"),
                ],
            ),
        ],
    )


def _feature_card(icon: str, title: str, description: str, href: str, body, span: str) -> dcc.Link:
    return dcc.Link(
        href=href,
        className=f"feature-card reveal {span}",
        children=[
            html.Div(
                className="feature-card-head",
                children=[
                    _ICONS[icon],
                    html.Div(title, className="feature-card-title"),
                ],
            ),
            html.Div(description, className="feature-card-desc"),
            html.Div(body, className="feature-card-body"),
            html.Div(className="feature-card-foot", children=[
                html.Span("OPEN SECTION", className="feature-card-open"),
                html.Span("→", className="feature-card-arrow"),
            ]),
        ],
    )


def _news_section() -> html.Section:
    return html.Section(
        className="home-news",
        children=[
            html.Div(
                className="home-section-head home-news-head reveal",
                children=[
                    html.Div("LIVE", className="home-section-num"),
                    html.H2("Latest asset news"),
                    html.P("Real headlines pulled from crypto news feeds — opens the original story. Cards refresh automatically as new articles are published."),
                ],
            ),
            html.Div(id="home-news-cards", className="asset-grid home-news-grid"),
        ],
    )


def _feature_cards() -> html.Section:
    return html.Section(
        id="home-features",
        className="home-features",
        children=[
            html.Div(
                className="home-section-head reveal",
                children=[
                    html.Div("01", className="home-section-num"),
                    html.H2("Explore the platform"),
                    html.P("Every card opens the real section it describes — live charts, models and data."),
                ],
            ),
            html.Div(
                className="home-cards",
                children=[
                    # Wide: live market snapshot with a sparkline.
                    _feature_card(
                        "pulse", "Market Overview",
                        "Monitor cryptocurrency prices, market movements, trading volume, "
                        "sentiment and key market indicators from a single overview.",
                        "/overview",
                        html.Div(id="home-market-price-list", className="mini-market", children=[
                            html.Div(className="mini-market-row", children=[
                                html.Div(className="mini-market-symbol", children=[
                                    html.Span(className="hero-dot hero-dot-btc"),
                                    html.Span("BTC"),
                                ]),
                                html.Div("$67,421", className="mini-market-price"),
                                html.Div("+2.4%", className="mini-market-change text-positive"),
                            ]),
                            html.Div(className="mini-market-row", children=[
                                html.Div(className="mini-market-symbol", children=[
                                    html.Span(className="hero-dot hero-dot-eth"),
                                    html.Span("ETH"),
                                ]),
                                html.Div("$3,421", className="mini-market-price"),
                                html.Div("+1.7%", className="mini-market-change text-positive"),
                            ]),
                            dcc.Markdown(dangerously_allow_html=True, className="mini-market-spark",
                                         children=_sparkline_svg([])),
                        ]),
                        "span-7",
                    ),
                    _feature_card(
                        "chart", "Market Analysis",
                        "Explore technical indicators, momentum, volume, volatility, sentiment "
                        "and correlations engineered from historical market data.",
                        "/forecast",
                        html.Div(className="mini-chips", children=[
                            html.Span("RSI 14", className="chip"), html.Span("SMA 7/30", className="chip"),
                            html.Span("Bollinger", className="chip"), html.Span("VWAP", className="chip"),
                            html.Span("Volume", className="chip"), html.Span("Fear & Greed", className="chip"),
                            html.Span("Anomalies", className="chip"),
                        ]),
                        "span-5",
                    ),
                    _feature_card(
                        "forecast", "AI Forecasting",
                        "Compare XGBoost, ARIMA, Linear Regression and a naive baseline with "
                        "leakage-aware time-series validation, MAE, RMSE and directional accuracy.",
                        "/forecast",
                        dcc.Markdown(dangerously_allow_html=True, className="mini-forecast", children=(
                            "<svg viewBox='0 0 300 110' xmlns='http://www.w3.org/2000/svg' preserveAspectRatio='none'>"
                            "<path d='M6 92 L60 84 L110 88 L160 74 L205 78 L245 68 L294 72' fill='none' stroke='#1F3B5B' stroke-width='2.4'/>"
                            "<path d='M245 50 L280 42 L300 38 L300 118 L245 118 L245 50Z' fill='rgba(57,118,210,.12)'/>"
                            "<path d='M245 96 L280 88 L300 84' fill='none' stroke='#3976D2' stroke-width='2.4' stroke-dasharray='4 4'/>"
                            "</svg>")),
                        "span-5",
                    ),
                    _feature_card(
                        "risk", "Risk & Performance",
                        "Understand volatility, drawdowns, VaR and CVaR, risk-adjusted performance "
                        "and historical strategy behavior.",
                        "/risk",
                        html.Div(id="home-risk-chips", className="mini-chips", children=[
                            html.Span("VOLATILITY 42.8%", className="chip chip-stat"),
                            html.Span("MAX DD −28.4%", className="chip chip-stat"),
                            html.Span("SHARPE 0.91", className="chip chip-stat"),
                        ]),
                        "span-7",
                    ),
                    _feature_card(
                        "gauge", "Market Intelligence",
                        "Combine momentum, technicals, sentiment and volatility into a transparent, "
                        "explainable 0–100 market score.",
                        "/overview",
                        html.Div(className="mini-gauge", children=[
                            html.Div(className="mini-gauge-score", children=[
                                html.Span(id="home-intel-score", className="mini-gauge-value", children="72"),
                                html.Span("/100", className="mini-gauge-max"),
                            ]),
                            html.Div(id="home-intel-label", className="mini-gauge-label", children="MODERATELY BULLISH"),
                            html.Div(id="home-intel-factors", className="mini-gauge-factors", children=[
                                html.Span("Momentum +", className="factor factor-pos"),
                                html.Span("Sentiment +", className="factor factor-pos"),
                                html.Span("Volatility −", className="factor factor-neg"),
                            ]),
                        ]),
                        "span-4",
                    ),
                    _feature_card(
                        "bell", "Alerts & Anomalies",
                        "Detect significant price moves, unusual volume, volatility spikes, "
                        "technical events and regime changes.",
                        "/alerts",
                        html.Div(id="home-alert-list", className="mini-alerts", children=[
                            html.Div("Alert feed loads live from the local database.", className="mini-alert-empty"),
                        ]),
                        "span-8",
                    ),
                    _feature_card(
                        "layers", "Model Explainability",
                        "Understand which features drive model predictions and why a particular "
                        "forecast was generated.",
                        "/explainability",
                        html.Div(className="mini-bars", children=[
                            html.Div(className="mini-bar", style={"width": "92%"}),
                            html.Div(className="mini-bar", style={"width": "74%"}),
                            html.Div(className="mini-bar", style={"width": "58%"}),
                            html.Div(className="mini-bar", style={"width": "38%"}),
                            html.Div(className="mini-bar", style={"width": "22%"}),
                        ]),
                        "span-4",
                    ),
                    _feature_card(
                        "loop", "Backtesting",
                        "Test trading strategies against historical data and compare performance "
                        "with a buy-and-hold baseline, every trade paying the same cost.",
                        "/strategy",
                        dcc.Markdown(dangerously_allow_html=True, className="mini-backtest", children=(
                            "<svg viewBox='0 0 300 100' xmlns='http://www.w3.org/2000/svg' preserveAspectRatio='none'>"
                            "<path d='M6 90 L70 86 L130 78 L190 66 L250 58 L294 50' fill='none' stroke='#1F3B5B' stroke-width='2.2'/>"
                            "<path d='M6 92 L70 90 L130 88 L190 88 L250 86 L294 84' fill='none' stroke='#9AA29D' stroke-width='2' stroke-dasharray='5 4'/>"
                            "<text x='240' y='46' fill='#9AA29D' font-size='10'>Strategy</text>"
                            "<text x='238' y='96' fill='#9AA29D' font-size='10'>Buy & Hold</text>"
                            "</svg>")),
                        "span-8",
                    ),
                ],
            ),
        ],
    )


def _section_index() -> html.Section:
    entries = [
        ("02", "Market Overview", "See the market clearly.",
         "Regime, market score, momentum, relationships and the intelligence feed for every tracked asset.",
         "/overview", "Open overview"),
        ("03", "Market Analysis", "Understand what is driving the market.",
         "Price, moving averages, RSI, Bollinger Bands, VWAP, volume, Fear & Greed and the market assistant.",
         "/forecast", "Open forecast lab"),
        ("04", "AI Forecasting", "Evidence-based forecasts with honest uncertainty.",
         "Leakage-aware model comparison with MAE, RMSE and directional accuracy, plus Excel exports.",
         "/forecast", "Open forecast lab"),
        ("05", "Risk Analytics", "Know the downside before you size a position.",
         "Annualized volatility, maximum drawdown, historical and parametric VaR, CVaR, Sharpe, Sortino and Calmar.",
         "/risk", "Open risk analytics"),
        ("06", "Market Intelligence", "A transparent score, never a black box.",
         "Six explainable factors — momentum, trend, sentiment, volume, volatility and RSI — sum to a 0–100 score.",
         "/overview", "Open overview"),
        ("07", "Alerts & Anomalies", "Know when the market moves.",
         "Price-movement, RSI, Bollinger, volume and volatility alerts with timestamps, severity and affected asset.",
         "/alerts", "Open signals & alerts"),
        ("08", "Explainability & Backtesting", "See why, then test what-if.",
         "SHAP feature contributions for the latest forecast and a six-strategy backtest with transaction costs.",
         "/strategy", "Open strategy lab"),
    ]
    return html.Section(
        className="home-sections",
        children=[
            html.Div(
                className="home-section-head reveal",
                children=[
                    html.Div("SECTIONS", className="home-section-num"),
                    html.H2("The research workstation"),
                    html.P("Seven focused pages, one shared data layer and a single focused asset that follows you everywhere."),
                ],
            ),
            html.Div(
                className="home-section-list",
                children=[
                    html.Div(
                        className="home-section-row reveal",
                        children=[
                            html.Div(num, className="home-section-row-num"),
                            html.Div(
                                className="home-section-row-main",
                                children=[
                                    html.Div(title, className="home-section-row-title"),
                                    html.Div(tagline, className="home-section-row-tagline"),
                                    html.Div(sentence, className="home-section-row-desc"),
                                ],
                            ),
                            dcc.Link(f"{link_label} →", href=href, className="home-section-row-link"),
                        ],
                    )
                    for num, title, tagline, sentence, href, link_label in entries
                ],
            ),
        ],
    )


def _footer() -> html.Footer:
    return html.Footer(
        className="home-footer",
        children=[
            html.Div(
                className="home-footer-grid",
                children=[
                    html.Div(
                        className="home-footer-brand",
                        children=[
                            html.Div(className="home-footer-logo", children=[
                                dcc.Markdown(dangerously_allow_html=True, className="home-logo", children=_logo_svg()),
                                html.Span("AI Market Intelligence", className="home-footer-name"),
                            ]),
                            html.P(
                                "A local, data-driven cryptocurrency analytics and forecasting "
                                "platform built for research and educational purposes.",
                                className="home-footer-desc",
                            ),
                        ],
                    ),
                    html.Div(
                        className="home-footer-col",
                        children=[
                            html.Div("Platform", className="home-footer-head"),
                            dcc.Link("Market Overview", href="/overview", className="home-footer-link"),
                            dcc.Link("Markets", href="/markets", className="home-footer-link"),
                            dcc.Link("Forecast Lab", href="/forecast", className="home-footer-link"),
                            dcc.Link("Risk Analytics", href="/risk", className="home-footer-link"),
                        ],
                    ),
                    html.Div(
                        className="home-footer-col",
                        children=[
                            html.Div("Research", className="home-footer-head"),
                            dcc.Link("Strategy Lab", href="/strategy", className="home-footer-link"),
                            dcc.Link("Explainability", href="/explainability", className="home-footer-link"),
                            dcc.Link("Signals & Alerts", href="/alerts", className="home-footer-link"),
                            dcc.Link("System", href="/system", className="home-footer-link"),
                        ],
                    ),
                    html.Div(
                        className="home-footer-col",
                        children=[
                            html.Div("Resources", className="home-footer-head"),
                            html.A("API documentation", href="http://127.0.0.1:8000/api",
                                   className="home-footer-link", target="_blank"),
                            dcc.Link("Model experiments", href="/system", className="home-footer-link"),
                            dcc.Link("Project layout", href="/system", className="home-footer-link"),
                        ],
                    ),
                ],
            ),
            html.Div(className="home-footer-legal", children=[
                html.Span("© 2026 AI Market Intelligence Platform · Built with Dash, Flask, scikit-learn & XGBoost"),
                html.P(
                    "This platform does not provide financial advice. Forecasts and analytical "
                    "outputs are educational and should not be used as the sole basis for financial decisions.",
                    className="home-disclaimer",
                ),
            ]),
        ],
    )


def layout_home() -> html.Div:
    return html.Div(
        className="home",
        children=[
            _nav_bar(),
            _hero(),
            _news_section(),
            _feature_cards(),
            _section_index(),
            _footer(),
        ],
    )
