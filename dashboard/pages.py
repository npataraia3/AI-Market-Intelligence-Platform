"""Static page scaffolds.

Each page is a skeleton of cards and containers; Dash callbacks in
``dash_app.py`` populate the element ids defined here. Keeping the
layouts declarative means the shell (sidebar/top bar/router) stays
independent of page content.
"""

from __future__ import annotations

from dash import dcc, html

from dashboard.components import help_badge, page_heading

PERIOD_OPTIONS = [{"label": f"Last {d} day(s)", "value": d} for d in (1, 7, 30, 90, 365)]
HORIZON_OPTIONS = [
    {"label": "1 month", "value": 30},
    {"label": "3 months", "value": 90},
    {"label": "6 months", "value": 180},
    {"label": "1 year", "value": 365},
    {"label": "3 years", "value": 1095},
]


def _two_col(left, right) -> html.Div:
    return html.Div(
        [
            html.Div(left, className="card"),
            html.Div(right, className="card"),
        ],
        className="grid-2",
    )


def layout_overview() -> html.Div:
    return html.Div(
        [
            page_heading(
                "Market Overview",
                "Live cross-asset picture: regime, momentum, relationships and the intelligence feed.",
                "Every figure on this page is recomputed from the latest market snapshot plus a 90-day historical window served by the local API.",
            ),
            html.Div(id="overview-strip", className="strip", style={"margin": "4px 0 16px"}),
            html.Div(
                [
                    html.Div(className="card-title", children=["Live news intelligence", help_badge("Every card is the latest real article for that asset, pulled live from public news feeds. Click the headline or the “Source · time ↗” footer to open the exact story in a new tab; “Analyze impact →” opens the forecast. The price stays as a small quote in the corner.")]),
                    html.Div(id="asset-cards", className="asset-grid"),
                ],
                style={"margin-bottom": "16px"},
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(className="card-title", children=["Relative performance · 90 days", help_badge("Each series is indexed so its first day equals 100. Steeper lines = stronger momentum.")]),
                            dcc.Graph(id="rel-performance-chart", config={"displayModeBar": False}),
                        ],
                        className="card",
                        style={"margin-bottom": "16px"},
                    ),
                ]
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(className="card-title", children=["Market relationships", help_badge("Pearson correlation of daily returns over the last 90 days, ranked by absolute strength.")]),
                            html.Div(id="correlation-list"),
                            html.Div([dcc.Link("View full correlation matrix →", href="/markets")], style={"margin-top": "10px"}),
                        ],
                        className="card",
                    ),
                    html.Div(
                        [
                            html.Div(className="card-title", children=["Forecast Lab", help_badge("Price history, indicators, forecast and model evaluation for the focused asset.")]),
                            html.Small(
                                "Generate and download forecasts for the selected cryptocurrency and time period — "
                                "both the analysis report and the forecast export are built as Excel files.",
                                className="note",
                            ),
                            html.Div([dcc.Link("Open forecast lab →", href="/forecast")], style={"margin-top": "10px"}),
                        ],
                        className="card",
                    ),
                    html.Div(
                        [
                            html.Div(className="card-title", children=["Intelligence feed", help_badge("Alerts persisted by the monitoring service: 24h moves, RSI extremes, Bollinger breaks, volume and volatility spikes, regime changes.")]),
                            html.Div(id="overview-alert-feed"),
                            html.Div([dcc.Link("Open signals & alerts →", href="/alerts")], style={"margin-top": "10px"}),
                        ],
                        className="card",
                    ),
                ],
                className="grid-3",
            ),
        ]
    )


def layout_markets() -> html.Div:
    return html.Div(
        [
            page_heading(
                "Markets",
                "Cross-asset leaderboard, correlation structure and normalized performance.",
                "The leaderboard is computed from the last 90 days of daily closes per tracked asset.",
            ),
            html.Div(
                [html.Div(className="card-title", children=["Leaderboard"]),
                 html.Div(id="leaderboard")],
                className="card",
                style={"margin-bottom": "16px"},
            ),
            _two_col(
                [
                    html.Div(className="card-title", children=["Correlation matrix", help_badge("Pearson correlation of daily returns. Red = strongly positive co-movement.")]),
                    dcc.Graph(id="correlation-chart", config={"displayModeBar": False}),
                ],
                [
                    html.Div(className="card-title", children=["Normalized performance", help_badge("First day = 100. Lines are drawn from the same 90-day window as the leaderboard.")]),
                    dcc.Graph(id="normalized-chart", config={"displayModeBar": False}),
                ],
            ),
        ]
    )


def layout_analysis() -> html.Div:
    return html.Div(
        [
            page_heading(
                "Forecast Lab",
                "Price history, indicators, forecast and model evaluation for the focused asset.",
                "The forecast is an ensemble of ARIMA, Random Forest and XGBoost baselines with a widening 95% prediction interval.",
            ),
            html.Div(id="analysis-header", style={"margin-bottom": "16px"}),
            _two_col(
                [
                    html.Div(className="card-title", children=["Price history & moving averages"]),
                    dcc.Graph(id="price-chart", config={"displayModeBar": False}),
                ],
                [
                    html.Div(className="card-title", children=["Candlestick & trading volume"]),
                    dcc.Graph(id="candle-chart", config={"displayModeBar": False}),
                ],
            ),
            html.Div(
                [
                    html.Div(className="card-title", children=["RSI, model forecast & 95% interval", help_badge("A flat point forecast is expected: crypto prices behave close to a random walk. The widening band is the honest uncertainty.")]),
                    dcc.Graph(id="forecast-chart", config={"displayModeBar": False}),
                ],
                className="card",
                style={"margin-top": "16px"},
            ),
            html.Div(
                [
                    html.Div(className="card-title", children=["Model evaluation · rolling time-series backtest", help_badge("Models are scored only on future folds, never a random split, to reduce time-series leakage.")]),
                    html.Div(id="model-table"),
                    html.P(
                        "The persistence (naive) baseline is “predict the last price” — selected models should beat it.",
                        className="note",
                    ),
                ],
                className="card",
                style={"margin-top": "16px"},
            ),
            html.Div(
                [
                    html.Div(className="card-title", children=["Market assistant"]),
                    html.Div(id="assistant-box"),
                    html.Div(
                        [
                            html.Div("Analysis period", className="stat-label", style={"margin": "14px 0 4px"}),
                            dcc.Dropdown(id="period-select", value=365, options=PERIOD_OPTIONS, clearable=False),
                            html.Small("CoinGecko’s free API caps historical data at 365 days.", className="note"),
                            html.Div("Forecast period", className="stat-label", style={"margin": "14px 0 4px"}),
                            dcc.Dropdown(id="forecast-horizon", value=90, options=HORIZON_OPTIONS, clearable=False),
                            html.Div(
                                [
                                    html.Button("Download detailed analysis (.xlsx)", id="download-analysis-button", n_clicks=0, className="btn", style={"margin-right": "8px"}),
                                    html.Button("Generate & download forecast (.xlsx)", id="forecast-button", n_clicks=0, className="btn"),
                                ],
                                style={"margin-top": "14px"},
                            ),
                            html.Small(
                                "Horizons beyond 90 days use an ARIMA baseline; 95% intervals widen with the horizon to reflect accumulating uncertainty.",
                                className="note",
                            ),
                        ]
                    ),
                ],
                className="card",
                style={"margin-top": "16px"},
            ),
        ]
    )


def layout_strategy() -> html.Div:
    return html.Div(
        [
            page_heading(
                "Strategy Lab",
                "Backtested trading strategies for the focused asset, every trade paying the same 0.2% cost.",
                "Strategies are BUY&HOLD, SMA crossovers, RSI reversion, momentum and Bollinger band — all compared apples-to-apples.",
            ),
            html.Div(id="strategy-header", style={"margin-bottom": "16px"}),
            html.Div(
                [
                    html.Div(className="card-title", children=["Backtest leaderboard · 365 days"]),
                    html.Div(id="backtest-table"),
                ],
                className="card",
                style={"margin-bottom": "16px"},
            ),
            html.Div(
                [
                    html.Div(className="card-title", children=["Strategy equity curves", help_badge("Equity starts at 1.0 for every strategy, so curves are directly comparable.")]),
                    dcc.Graph(id="backtest-equity-chart", config={"displayModeBar": False}),
                ],
                className="card",
            ),
        ]
    )


def layout_explainability() -> html.Div:
    return html.Div(
        [
            page_heading(
                "Explainability",
                "Why the model says what it says — local SHAP contributions and global feature influence.",
                "SHAP values decompose the next-day return forecast into per-feature contributions for the most recent observation.",
            ),
            html.Div(id="explain-header", style={"margin-bottom": "16px"}),
            _two_col(
                [
                    html.Div(className="card-title", children=["Local explanation · most recent forecast", help_badge("Bars show how each feature pushed the forecast up or down for today’s observation.")]),
                    html.Div(id="local-explanation"),
                ],
                [
                    html.Div(className="card-title", children=["Feature influence · global importance", help_badge("Mean |SHAP| over all observations — the features that, on average, move the forecast most.")]),
                    dcc.Graph(id="shap-global-chart", config={"displayModeBar": False}),
                ],
            ),
            html.Div(
                [
                    html.Div(className="card-title", children=["Feature importance · what drives the forecast", help_badge("Gain-based importances from the XGBoost model fit on the full training window.")]),
                    dcc.Graph(id="importance-chart", config={"displayModeBar": False}),
                    html.Small(
                        "Every analysis run is logged to MLflow — run `mlflow ui` in the project folder — and recorded in logs/model_experiments.jsonl.",
                        className="note",
                    ),
                ],
                className="card",
                style={"margin-top": "16px"},
            ),
            html.Div(
                [
                    html.Div(className="card-title", children=["Signal backtest · model vs buy & hold", help_badge("BUY/HOLD labels come from the XGBoost forecast; bars show realized next-day returns.")]),
                    dcc.Graph(id="signals-chart", config={"displayModeBar": False}),
                ],
                className="card",
                style={"margin-top": "16px"},
            ),
        ]
    )


def layout_intelligence() -> html.Div:
    return html.Div(
        [
            page_heading(
                "Signals & Alerts",
                "The full alert history persisted by the monitoring service, plus model drift and data quality.",
                "Alerts live in the local SQLite database (alerts table) and are served by /api/alerts.",
            ),
            html.Div(id="intel-header", style={"margin-bottom": "16px"}),
            html.Div(
                [
                    html.Div(className="card-title", children=["Alert history"]),
                    html.Div(
                        [
                            html.Label("Severity", className="stat-label"),
                            dcc.Dropdown(
                                id="alert-filter",
                                value="all",
                                clearable=False,
                                options=[
                                    {"label": "All severities", "value": "all"},
                                    {"label": "High", "value": "high"},
                                    {"label": "Medium", "value": "medium"},
                                ],
                                style={"width": "220px", "margin": "6px 0 12px"},
                            ),
                        ]
                    ),
                    html.Div(id="alerts-table"),
                ],
                className="card",
                style={"margin-bottom": "16px"},
            ),
            _two_col(
                [html.Div(className="card-title", children=["Model drift"]), html.Div(id="drift-status")],
                [html.Div(className="card-title", children=["Data quality"]), html.Div(id="quality-box")],
            ),
        ]
    )


def layout_system() -> html.Div:
    return html.Div(
        [
            page_heading(
                "System",
                "Data pipeline health, storage and model experiment log for the focused asset.",
                "Snapshots are collected on demand and retained in SQLite; model runs are appended to logs/model_runs.jsonl.",
            ),
            html.Div(
                [
                    html.Div(className="card-title", children=["Data pipeline"]),
                    html.Div(
                        [
                            html.Button("Refresh market data now", id="refresh-button", n_clicks=0, className="btn-primary"),
                            html.Span(id="refresh-status", style={"margin-left": "12px"}),
                        ]
                    ),
                    html.Div(id="quality-box-system", style={"margin-top": "12px"}),
                    html.Small(
                        "Source: CoinGecko public market data. Historical analysis is retrieved on demand; snapshots are stored locally in SQLite.",
                        className="note",
                    ),
                ],
                className="card",
                style={"margin-bottom": "16px"},
            ),
            html.Div(
                [
                    html.Div(className="card-title", children=["Recent model runs", help_badge("Each row corresponds to a recorded market/analysis run for the focused asset.")]),
                    html.Div(id="model-runs"),
                ],
                className="card",
            ),
        ]
    )


def layout_risk() -> html.Div:
    return html.Div(
        [
            page_heading(
                "Risk Analytics",
                "Volatility, drawdowns, value-at-risk and risk-adjusted performance for the focused asset.",
                "All measures come from the observed price history — no model assumptions beyond the parametric VaR, which assumes normality and is reported alongside the fully non-parametric historical VaR.",
            ),
            html.Div(id="risk-header", style={"margin-bottom": "16px"}),
            html.Div(
                [
                    html.Div(className="card-title", children=["Risk snapshot · 90 days", help_badge("Annualized where noted; VaR is reported for a single day at 95% confidence.")]),
                    html.Div(id="risk-stats", className="strip", style={"margin-top": "4px"}),
                ],
                className="card",
                style={"margin-bottom": "16px"},
            ),
            _two_col(
                [
                    html.Div(className="card-title", children=["Historical drawdown", help_badge("Cumulative drawdown from the running peak; the lowest point is the maximum drawdown.")]),
                    dcc.Graph(id="drawdown-chart", config={"displayModeBar": False}),
                ],
                [
                    html.Div(className="card-title", children=["Value at risk · 95% confidence", help_badge("The estimated one-day loss you should not exceed at 95% confidence. Historical VaR makes no distributional assumption.")]),
                    html.Div(id="var-panel"),
                ],
            ),
            html.Div(
                [
                    html.Div(className="card-title", children=["How to read this"]),
                    html.P(
                        "Sharpe, Sortino and Calmar compare return against different risk measures "
                        "(total volatility, downside deviation and maximum drawdown respectively). "
                        "Max drawdown describes the worst peak-to-trough loss in the window. None of "
                        "these are forward-looking guarantees.",
                        className="note",
                    ),
                ],
                className="card",
                style={"margin-top": "16px"},
            ),
        ]
    )
