from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

# Make the project root importable regardless of the launch directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from dash import ALL, Dash, Input, Output, State, dcc, dash_table, html, no_update

from app.core.config import settings
from app.services.reporting import build_analysis_excel_report, build_forecast_excel_report

from dashboard import home, pages
from dashboard.components import (
    _fixed,
    alert_item,
    base_table,
    fmt_pct,
    help_badge,
    insight_card,
    pill,
    price_format,
    stat_card,
)
from dashboard.theme import TOKENS, apply_theme, css, empty_figure

PALETTE = TOKENS["chart_palette"]
DEFAULT_COIN = settings.tracked_coins[0]
TRACKED_COINS = list(settings.tracked_coins)

# Compact visual identity for the news cards. Glyphs fall back to the ticker.
_COIN_GLYPHS = {
    "bitcoin": "₿",
    "ethereum": "Ξ",
    "binancecoin": "◆",
    "solana": "◎",
    "dogecoin": "Ð",
}
# Title-matching terms used to prefer the most *relevant* recent article for a
# card (an article that names the asset in its headline over a vague mention).
_COIN_TITLE_TERMS = {
    "bitcoin": ("bitcoin", "btc"),
    "ethereum": ("ethereum", "eth"),
    "binancecoin": ("binance", "bnb", "binance coin"),
    "solana": ("solana", "sol"),
    "dogecoin": ("dogecoin", "doge"),
}
_COIN_TITLE_RES = {
    coin: re.compile(r"\b(?:" + "|".join(re.escape(t) for t in terms) + r")\b", re.IGNORECASE)
    for coin, terms in _COIN_TITLE_TERMS.items()
}

API_URL = os.getenv("MARKET_API_URL", "http://127.0.0.1:8000/api").rstrip("/")
_HTTP = requests.Session()
_HTTP.trust_env = False

LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
MODEL_RUNS_FILE = LOGS_DIR / "model_runs.jsonl"


def api_get(path: str, **params) -> dict | list:
    response = _HTTP.get(f"{API_URL}{path}", params=params, timeout=60)
    response.raise_for_status()
    return response.json()


def refresh_market() -> dict:
    response = _HTTP.post(f"{API_URL}/market/refresh", timeout=60)
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------- pages

# Single source of truth for navigation. Every section, sidebar item and
# route below derives from this registry; aliases keep old URLs working.
PAGES = [
    {"id": "overview", "label": "Overview", "path": "/overview", "section": "MARKET"},
    {"id": "markets", "label": "Markets", "path": "/markets", "section": "MARKET"},
    {"id": "forecast", "label": "Forecast Lab", "path": "/forecast", "section": "ANALYSIS"},
    {"id": "risk", "label": "Risk", "path": "/risk", "section": "ANALYSIS"},
    {"id": "strategy", "label": "Strategy Lab", "path": "/strategy", "section": "MODELS"},
    {"id": "explainability", "label": "Explainability", "path": "/explainability", "section": "MODELS"},
    {"id": "alerts", "label": "Signals & Alerts", "path": "/alerts", "section": "INTELLIGENCE"},
    {"id": "system", "label": "System", "path": "/system", "section": "INTELLIGENCE"},
]
ROUTE_ALIASES = {
    "/analysis": "/forecast",
    "/strategy-lab": "/strategy",
    "/intelligence": "/alerts",
}
PAGE_BY_ID = {page["id"]: page for page in PAGES}
PAGE_PATHS = {page["path"] for page in PAGES}
NAV_SECTIONS = []
for section in ("MARKET", "ANALYSIS", "MODELS", "INTELLIGENCE"):
    items = [(page["id"], page["label"], page["path"]) for page in PAGES if page["section"] == section]
    if items:
        NAV_SECTIONS.append((section, items))

# ---------------------------------------------------------------- shell

app = Dash(__name__, title="AI Market Intelligence Platform")

_INDEX_STRING = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        <style>
{style}
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
        <script>
        (function () {
            function initReveal() {
                var els = document.querySelectorAll('.reveal:not([data-reveal])');
                if (!els.length) return;
                var io = new IntersectionObserver(function (entries) {
                    entries.forEach(function (entry) {
                        if (entry.isIntersecting) {
                            entry.target.classList.add('revealed');
                            io.unobserve(entry.target);
                        }
                    });
                }, { threshold: 0.12 });
                els.forEach(function (el) { el.setAttribute('data-reveal', '1'); io.observe(el); });
            }
            document.addEventListener('click', function (event) {
                var anchor = event.target && event.target.closest ? event.target.closest('a[href^="#"]') : null;
                if (!anchor) return;
                var target = document.querySelector(anchor.getAttribute('href'));
                if (target) { event.preventDefault(); target.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
            });
            window.addEventListener('load', initReveal);
            setTimeout(initReveal, 1500);
        })();
        </script>
    </body>
</html>
""".replace("{style}", css())
app.index_string = _INDEX_STRING

NAV_IDS = [page["id"] for page in PAGES]
PAGE_IDS = [f"page-{page['id']}" for page in PAGES]

nav_children = []
for section_label, items in NAV_SECTIONS:
    nav_children.append(html.Div(section_label, className="nav-section-label"))
    for item_id, label, href in items:
        nav_children.append(dcc.Link(label, id=f"nav-{item_id}", href=href, className="nav-item"))

app.layout = html.Div(
    [
        dcc.Store(id="data-store", data={}),
        dcc.Store(id="active-coin", data=DEFAULT_COIN),
        dcc.Store(id="refresh-signal", data=None),
        dcc.Store(id="news-retry-signal", data=0),
        dcc.Location(id="url", refresh=False),
        dcc.Interval(id="refresh-interval", interval=5 * 60 * 1000, n_intervals=0),
        dcc.Download(id="download-analysis"),
        dcc.Download(id="download-forecast"),
        html.Div(id="home-root", children=home.layout_home()),
        html.Div(
            id="dash-app-shell",
            className="dash-app-shell",
            style={"display": "none"},
            children=[
                html.Div(
                    className="sidebar",
                    children=[
                        html.Div(
                            [
                                html.Div("AI Market Intelligence", className="sidebar-brand-title"),
                                html.Div("Market Research Workstation", className="sidebar-brand-sub"),
                            ],
                            className="sidebar-brand",
                        ),
                        html.Div(nav_children, className="sidebar-nav"),
                        html.Div(id="sidebar-status", className="sidebar-footer"),
                    ],
                ),
                html.Div(
                    className="main",
                    children=[
                        html.Div(
                            className="topbar",
                            children=[
                                html.Div(id="topbar-page", className="topbar-page", children="OVERVIEW"),
                                html.Div(id="active-coin-label", style={"font-weight": 700, "font-size": "13px"}),
                                html.Div(className="topbar-spacer"),
                                html.Div(
                                    [
                                        dcc.Dropdown(
                                            id="coin-search",
                                            value=DEFAULT_COIN,
                                            clearable=False,
                                            options=[{"label": coin.replace("-", " ").title(), "value": coin}
                                                     for coin in TRACKED_COINS],
                                            style={"width": "220px"},
                                        ),
                                    ]
                                ),
                                html.Div([html.Span(className="live-dot"), html.Span("LIVE", className="live-label")],
                                         style={"display": "flex", "align-items": "center", "gap": "6px"}),
                            ],
                        ),
                        html.Div(
                            className="page",
                            children=[
                                dcc.Loading(
                                    id="page-loading",
                                    parent_className="page-loading-wrap",
                                    overlay_style={"visibility": "visible", "filter": "blur(1px)"},
                                    children=[
                                        html.Div(id="page-overview", children=pages.layout_overview()),
                                        html.Div(id="page-markets", children=pages.layout_markets(), style={"display": "none"}),
                                        html.Div(id="page-forecast", children=pages.layout_analysis(), style={"display": "none"}),
                                        html.Div(id="page-risk", children=pages.layout_risk(), style={"display": "none"}),
                                        html.Div(id="page-strategy", children=pages.layout_strategy(), style={"display": "none"}),
                                        html.Div(id="page-explainability", children=pages.layout_explainability(), style={"display": "none"}),
                                        html.Div(id="page-alerts", children=pages.layout_intelligence(), style={"display": "none"}),
                                        html.Div(id="page-system", children=pages.layout_system(), style={"display": "none"}),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        ),
    ],
)


# ---------------------------------------------------------------- routing

HOME_PATHS = {"/", "", "/home"}


@app.callback(
    Output("home-root", "style"),
    Output("dash-app-shell", "style"),
    *[Output(f"page-{page['id']}", "style") for page in PAGES],
    Output("topbar-page", "children"),
    *[Output(f"nav-{page['id']}", "className") for page in PAGES],
    Input("url", "pathname"),
)
def router(pathname: str):
    pathname = pathname or "/"
    page_styles = [{"display": "none"} for _ in PAGES]
    if pathname in HOME_PATHS:
        home_style = {"display": "block"}
        shell_style = {"display": "none"}
        page_label = "Overview"
        active = None
    else:
        pathname = ROUTE_ALIASES.get(pathname, pathname)
        home_style = {"display": "none"}
        # Inline styles replace the stylesheet rule, so the flex row must be
        # restated here or the sidebar/main layout collapses.
        shell_style = {"display": "flex"}
        if pathname not in PAGE_PATHS:
            pathname = "/overview"
        for index, page in enumerate(PAGES):
            page_styles[index] = {"display": "block" if page["path"] == pathname else "none"}
        active = next((page["id"] for page in PAGES if page["path"] == pathname), None)
        page_label = next((page["label"] for page in PAGES if page["path"] == pathname), "Overview")
    nav_classes = ["nav-item active" if page["id"] == active else "nav-item" for page in PAGES]
    return [home_style, shell_style, *page_styles, page_label, *nav_classes]


@app.callback(
    Output("active-coin", "data"),
    Input("coin-search", "value"),
    Input("url", "search"),
)
def set_active_coin(selected: str, search: str):
    if selected:
        return selected
    if search:
        params = urllib.parse.parse_qs(search.lstrip("?"))
        coin = params.get("coin", [None])[0]
        if coin and coin in TRACKED_COINS:
            return coin
    return no_update


# ---------------------------------------------------------------- data

@app.callback(
    Output("data-store", "data"),
    Input("refresh-interval", "n_intervals"),
    Input("refresh-signal", "data"),
    Input("active-coin", "data"),
    Input("period-select", "value"),
    Input("news-retry-signal", "data"),
)
def load_data(n_intervals: int, refresh_signal, coin_id: str, period: int, news_retry: int) -> dict:
    coin_id = coin_id or DEFAULT_COIN
    period = period or 365
    store = {"snapshots": [], "snapshots_error": None, "analysis": None, "analysis_error": None,
             "summary": "", "alerts": [], "alerts_error": None, "news": None, "news_error": None,
             "news_meta": None,
             "overview": None, "comparison": None, "regime": None, "risk": None,
             "score": None, "backtest": None, "drift": None, "data_quality": None,
             "api_health": "unknown"}

    jobs = [
        ("snapshots", "/market/snapshots", {"limit": 500}),
        ("overview", "/market/overview", {}),
        ("comparison", "/market/comparison", {"days": 90}),
        ("regime", f"/market/regime/{coin_id}", {"days": 90}),
        ("risk", f"/market/risk/{coin_id}", {"days": 90}),
        ("score", f"/market/score/{coin_id}", {"days": 90}),
        ("backtest", f"/market/backtest/{coin_id}", {"days": 365}),
        ("drift", "/monitoring/drift", {"coin_id": coin_id}),
        ("data_quality", f"/market/data-quality/{coin_id}", {"days": 90}),
        ("analysis", f"/market/analysis/{coin_id}", {"days": period}),
        ("summary", "/assistant/summary", {"coin_id": coin_id}),
        ("alerts", "/alerts", {"limit": 100}),
        ("news", "/news", {"limit": 100}),
    ]

    _ERROR_KEYS = {"snapshots": "snapshots_error", "analysis": "analysis_error",
                   "alerts": "alerts_error", "news": "news_error"}

    def fetch(job):
        key, path, kwargs = job
        try:
            return key, api_get(path, **kwargs), None, None
        except requests.RequestException as exc:
            return key, None, _ERROR_KEYS.get(key, ""), str(exc)

    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        results = list(pool.map(fetch, jobs))

    for key, value, error_key, error_message in results:
        if error_key:
            store[error_key] = error_message
            continue
        if key == "analysis":
            store[key] = value
        elif key == "summary":
            store[key] = (value or {}).get("summary") or "Refresh current market data to generate a local summary."
        elif key == "news":
            store["news"] = (value or {}).get("news") or []
            store["news_meta"] = {"fetched_at": (value or {}).get("fetched_at"),
                                  "error": (value or {}).get("error")}
        else:
            store[key] = value

    try:
        store["api_health"] = api_get("/health")["status"]
    except requests.RequestException:
        store["api_health"] = "offline"
    return store


@app.callback(
    Output("news-retry-signal", "data"),
    Input({"type": "news-retry", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def news_retry(n_clicks: list[int]) -> int:
    return max([n for n in n_clicks if n] or [0])


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
            html.Span(f"Saved {result['saved']} new snapshots.", style={"color": TOKENS["positive"]})
    except Exception as exc:
        return None, html.Span(f"Refresh failed: {exc}", style={"color": TOKENS["negative"]})


@app.callback(
    Output("coin-search", "options"),
    Output("active-coin-label", "children"),
    Input("data-store", "data"),
    Input("active-coin", "data"),
)
def update_coin_controls(store: dict, active_coin: str):
    store = store or {}
    active_coin = active_coin or DEFAULT_COIN
    labels = {coin: coin.replace("-", " ").title() for coin in TRACKED_COINS}
    snapshots = store.get("snapshots") or []
    if snapshots:
        frame = pd.DataFrame(snapshots)
        latest = frame.sort_values("captured_at", ascending=False).drop_duplicates("coin_id")
        for _, row in latest.iterrows():
            labels[row["coin_id"]] = f"{row['name']} ({row['symbol'].upper()})"
    options = [{"label": label, "value": coin} for coin, label in labels.items()]
    current = labels.get(active_coin, active_coin.replace("-", " ").title())
    return options, html.Span(f"{current.upper()}")


# ---------------------------------------------------------------- overview

def _regime_style(regime: str) -> tuple[str, str]:
    lowered = (regime or "").upper()
    if "BULL" in lowered:
        return TOKENS["positive"], "Bull market"
    if "BEAR" in lowered:
        return TOKENS["negative"], "Bear market"
    if "NEUTRAL" in lowered or "RANGE" in lowered:
        return TOKENS["warning"], "Neutral / ranging"
    return TOKENS["accent_2"], regime


def _time_ago(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        published = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    minutes = max(0, int((datetime.now(timezone.utc) - published.astimezone(timezone.utc)).total_seconds() // 60))
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes} min ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    if days < 7:
        return f"{days}d ago"
    return published.strftime("%b %-d") if not sys.platform.startswith("win") else published.strftime("%b %d")


def _pick_coin_article(articles: list[dict], coin: str) -> dict | None:
    """Most recent *relevant* article for a coin: prefer a headline that names
    the asset, then one that ships a thumbnail, so cards render nicely while
    staying fully data-driven."""
    matches = [a for a in articles if coin in (a.get("coins") or [])]
    if not matches:
        return None
    pattern = _COIN_TITLE_RES.get(coin)
    for article in matches:  # already recency-sorted by the API
        if pattern and pattern.search(article.get("title") or "") and article.get("image"):
            return article
    for article in matches:
        if pattern and pattern.search(article.get("title") or ""):
            return article
    for article in matches:
        if article.get("image"):
            return article
    return matches[0]


def _name_parts(label: str) -> tuple[str, str]:
    """Split "Bitcoin (BTC)" into ("Bitcoin", "BTC")."""
    match = re.search(r"^(.*?)\s*\(([^)]+)\)\s*$", label)
    if match:
        return match.group(1).strip(), match.group(2).upper()
    return label, ""


def _asset_news_block(article: dict | None, coin: str,
                      fetched_at: str | None, state: str) -> list:
    """News-first body for one asset card.

    ``state`` is one of "loading", "error", "empty", "ready" and mirrors the
    news feed health; market data on the same card is never affected.
    """
    if state == "loading":
        return [
            html.Div(className="asset-news asset-news-loading", children=[
                html.Div("Loading latest news…", className="asset-news-hint"),
                html.Div(className="asset-skeleton"),
                html.Div("Fetching current articles", className="asset-news-hint"),
            ]),
        ]
    if state == "error":
        return [
            html.Div(className="asset-news asset-news-error", children=[
                html.Div("Latest news unavailable right now.", className="asset-news-hint"),
                html.Button("Retry", id={"type": "news-retry", "index": coin},
                            className="asset-retry-btn", n_clicks=0),
            ]),
        ]
    if article is None:
        last = "Last checked · " + _time_ago(fetched_at) if fetched_at else ""
        return [
            html.Div(className="asset-news asset-news-empty", children=[
                html.Div("No recent relevant news found.", className="asset-news-hint"),
                html.Div(last, className="asset-news-meta") if last else None,
            ]),
        ]
    url = article.get("url") or "#"
    source = article.get("source") or "News"
    meta = " · ".join(part for part in (source, _time_ago(article.get("published_at"))) if part)
    image = article.get("image")
    thumb = html.Div(className="asset-thumb",
                     style={"backgroundImage": f"url('{image}')"}) if image else None
    return [
        html.Div(className="asset-news", children=[
            html.Div(className="asset-news-body", children=[
                thumb,
                html.A(article.get("title") or "", href=url, target="_blank",
                       rel="noopener noreferrer", title=article.get("title") or "",
                       className="asset-headline"),
            ]),
            html.Div(className="asset-news-foot", children=[
                html.A(f"{meta} ↗", href=url, target="_blank", rel="noopener noreferrer",
                       className="asset-news-source"),
                dcc.Link("Analyze impact →", href=f"/forecast?coin={coin}",
                         className="asset-news-analyze"),
            ]),
        ]),
    ]


@app.callback(
    Output("overview-strip", "children"),
    Output("asset-cards", "children"),
    Input("data-store", "data"),
    Input("active-coin", "data"),
)
def update_overview(store: dict, active_coin: str):
    store = store or {}
    active_coin = active_coin or DEFAULT_COIN

    strip_cards = []

    regime = store.get("regime") or {}
    regime_name = regime.get("consensus") or (regime.get("rule_based") or {}).get("regime", "Unknown")
    regime_color, regime_note = _regime_style(regime_name)
    strip_cards.append(stat_card("Market regime", regime_name, regime_note, tone="accent"))

    score = store.get("score") or {}
    if score.get("score") is not None:
        value = score["score"]
        tone = "positive" if value >= 60 else "warning" if value >= 40 else "negative"
        strip_cards.append(stat_card("Market score", f"{value:.0f}/100", score.get("label") or "", tone=tone))

    overview = store.get("overview") or {}
    fear_greed = overview.get("fear_greed") or {}
    if fear_greed.get("value") is not None:
        strip_cards.append(stat_card("Fear & Greed", f"{fear_greed['value']:.0f}/100", fear_greed.get("label") or ""))

    drift = store.get("drift") or {}
    if drift:
        if drift.get("drifted"):
            status, tone, detail = "DRIFT DETECTED", "negative", drift.get("detail") or ""
        elif drift.get("status") == "insufficient data":
            status, tone, detail = "tracking…", "neutral", drift.get("detail") or ""
        else:
            status, tone, detail = "healthy", "positive", drift.get("detail") or ""
        strip_cards.append(stat_card("Model drift", status, detail, tone=tone))

    comparison = store.get("comparison") or {}
    coins = comparison.get("coins") or []
    if coins:
        best = max(coins, key=lambda coin: (coin["performance_percent"].get("30d") or -999))
        best_30d = best["performance_percent"].get("30d")
        strip_cards.append(stat_card("Best 30d mover", best["coin_id"].replace("-", " ").title(),
                                     fmt_pct(best_30d) if best_30d is not None else "n/a"))

    snapshots = store.get("snapshots") or []
    labels = {coin: coin.replace("-", " ").title() for coin in TRACKED_COINS}
    if snapshots:
        frame = pd.DataFrame(snapshots)
        latest = frame.sort_values("captured_at", ascending=False).drop_duplicates("coin_id")
        for _, row in latest.iterrows():
            labels[row["coin_id"]] = f"{row['name']} ({row['symbol'].upper()})"

    news_items = store.get("news")
    news_meta = store.get("news_meta") or {}
    news_error = store.get("news_error") or news_meta.get("error")
    fetched_at = news_meta.get("fetched_at")

    cards = []
    for coin in TRACKED_COINS:
        meta = None
        perf = {}
        if coins:
            meta = next((item for item in coins if item["coin_id"] == coin), None)
            perf = (meta or {}).get("performance_percent") or {}
        active = coin == active_coin
        change = perf.get("24h")
        change_class = "text-positive" if (change or 0) > 0 else "text-negative" if (change or 0) < 0 else "text-secondary"
        display = labels.get(coin, coin.replace("-", " ").title())
        short_name, ticker = _name_parts(display)

        if news_items is None:
            news_state, article = "loading", None
        elif not news_items:
            news_state, article = ("error" if news_error else "empty"), None
        else:
            article = _pick_coin_article(news_items, coin)
            news_state = "ready" if article else "empty"

        price = (meta or {}).get("price_usd")
        price_str = price_format(price) if price is not None else None
        quote = None
        if price_str is not None or change is not None:
            quote = html.Div(className="asset-quote", children=[
                html.Div(price_str, className="asset-price-small"),
                html.Div(f"24h {fmt_pct(change)}" if change is not None else "24h —",
                         className=f"asset-change-small {change_class}"),
            ])

        cards.append(html.Div(
            className="asset-card active" if active else "asset-card",
            children=[
                html.Div(className="asset-card-head", children=[
                    html.Div(className="asset-id", children=[
                        html.Span(_COIN_GLYPHS.get(coin, ""), className="asset-glyph") if _COIN_GLYPHS.get(coin) else None,
                        html.Div(className="asset-name-block", children=[
                            dcc.Link(short_name.upper() if short_name else coin.replace("-", " ").upper(),
                                     href=f"/overview?coin={coin}", className="asset-card-name"),
                            html.Span(ticker, className="asset-ticker") if ticker else None,
                        ]),
                        html.Span("FOCUS", className="asset-focus-tag") if active else None,
                    ]),
                    quote,
                ]),
                *_asset_news_block(article, coin, fetched_at, news_state),
            ],
        ))

    return strip_cards, _asset_news_cards(store, active_coin)


def _asset_news_cards(store: dict, active_coin: str | None) -> list:
    """Per-asset news cards shared by the Overview page and the homepage.

    ``active_coin`` selects the highlighted "FOCUS" card (None on the landing
    page, where every card is presented equally).
    """
    store = store or {}
    snapshots = store.get("snapshots") or []
    labels = {coin: coin.replace("-", " ").title() for coin in TRACKED_COINS}
    if snapshots:
        frame = pd.DataFrame(snapshots)
        latest = frame.sort_values("captured_at", ascending=False).drop_duplicates("coin_id")
        for _, row in latest.iterrows():
            labels[row["coin_id"]] = f"{row['name']} ({row['symbol'].upper()})"
    coins = (store.get("comparison") or {}).get("coins") or []
    news_items = store.get("news")
    news_meta = store.get("news_meta") or {}
    news_error = store.get("news_error") or news_meta.get("error")
    fetched_at = news_meta.get("fetched_at")

    cards = []
    for coin in TRACKED_COINS:
        meta = None
        perf = {}
        if coins:
            meta = next((item for item in coins if item["coin_id"] == coin), None)
            perf = (meta or {}).get("performance_percent") or {}
        active = coin == active_coin
        change = perf.get("24h")
        change_class = "text-positive" if (change or 0) > 0 else "text-negative" if (change or 0) < 0 else "text-secondary"
        display = labels.get(coin, coin.replace("-", " ").title())
        short_name, ticker = _name_parts(display)

        if news_items is None:
            news_state, article = "loading", None
        elif not news_items:
            news_state, article = ("error" if news_error else "empty"), None
        else:
            article = _pick_coin_article(news_items, coin)
            news_state = "ready" if article else "empty"

        price = (meta or {}).get("price_usd")
        price_str = price_format(price) if price is not None else None
        quote = None
        if price_str is not None or change is not None:
            quote = html.Div(className="asset-quote", children=[
                html.Div(price_str, className="asset-price-small"),
                html.Div(f"24h {fmt_pct(change)}" if change is not None else "24h —",
                         className=f"asset-change-small {change_class}"),
            ])

        cards.append(html.Div(
            className="asset-card active" if active else "asset-card",
            children=[
                html.Div(className="asset-card-head", children=[
                    html.Div(className="asset-id", children=[
                        html.Span(_COIN_GLYPHS.get(coin, ""), className="asset-glyph") if _COIN_GLYPHS.get(coin) else None,
                        html.Div(className="asset-name-block", children=[
                            dcc.Link(short_name.upper() if short_name else coin.replace("-", " ").upper(),
                                     href=f"/overview?coin={coin}", className="asset-card-name"),
                            html.Span(ticker, className="asset-ticker") if ticker else None,
                        ]),
                        html.Span("FOCUS", className="asset-focus-tag") if active else None,
                    ]),
                    quote,
                ]),
                *_asset_news_block(article, coin, fetched_at, news_state),
            ],
        ))

    return cards


@app.callback(
    Output("rel-performance-chart", "figure"),
    Input("data-store", "data"),
)
def update_rel_performance(store: dict):
    empty = empty_figure(360)
    comparison = store.get("comparison") or {}
    normalized = (comparison.get("series") or {}).get("normalized_performance") or {}
    if not normalized:
        return empty
    fig = go.Figure()
    for coin, points in normalized.items():
        frame = pd.DataFrame(points)
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        fig.add_trace(go.Scatter(x=frame["timestamp"], y=frame["value"] * 100,
                                 mode="lines", name=coin, line=dict(width=2.5)))
    return apply_theme(fig, height=360, yaxis_title="Indexed (start = 100)")


@app.callback(
    Output("correlation-list", "children"),
    Input("data-store", "data"),
)
def update_correlation_list(store: dict):
    comparison = store.get("comparison") or {}
    matrix = comparison.get("correlation_matrix") or {}
    if not matrix:
        return [html.Div("No correlation data yet — history may be too short.", className="note")]
    frame = pd.DataFrame.from_dict(matrix)
    pairs = []
    for i, row in enumerate(frame.columns):
        for j in range(i + 1, len(frame.columns)):
            col = frame.columns[j]
            value = frame.iloc[i, j]
            if value is not None and pd.notna(value):
                pairs.append((frame.columns[i], col, float(value)))
    pairs.sort(key=lambda item: abs(item[2]), reverse=True)
    rows = []
    for a, b, value in pairs[:6]:
        tone = "positive" if value >= 0 else "negative"
        rows.append(html.Div(
            [
                html.Span(f"{a.replace('-', ' ').title()} ↔ {b.replace('-', ' ').title()}",
                          style={"flex": "1", "font-size": "12px", "font-weight": 600}),
                pill(f"{value:+.2f}", tone),
            ],
            style={"display": "flex", "align-items": "center", "gap": "10px", "padding": "5px 0",
                   "border-bottom": f"1px solid {TOKENS['border']}"},
        ))
    return rows


@app.callback(
    Output("overview-alert-feed", "children"),
    Input("data-store", "data"),
)
def update_overview_alerts(store: dict):
    alerts = store.get("alerts") or []
    if store.get("alerts_error"):
        return [html.Div(f"Alerts unavailable: {store['alerts_error']}", style={"color": TOKENS["negative"]})]
    if not alerts:
        return [html.Div("No significant movement or technical alerts recorded yet.", className="note")]
    return [alert_item(alert) for alert in alerts[:5]]


# ---------------------------------------------------------------- markets

@app.callback(
    Output("leaderboard", "children"),
    Output("correlation-chart", "figure"),
    Output("normalized-chart", "figure"),
    Input("data-store", "data"),
)
def update_markets(store: dict):
    empty = empty_figure(360)
    comparison = store.get("comparison") or {}
    coins = comparison.get("coins") or []
    if not coins:
        return (html.Div("No cross-asset comparison available yet — history may be too short.", className="note"),
                empty, empty)

    leaderboard = base_table(
        columns=[
            {"name": "Asset", "id": "coin_id"},
            {"name": "Price ($)", "id": "price_usd", "type": "numeric", "format": _fixed(2)},
            {"name": "24h %", "id": "perf24", "type": "numeric", "format": _fixed(2)},
            {"name": "7d %", "id": "perf7", "type": "numeric", "format": _fixed(2)},
            {"name": "30d %", "id": "perf30", "type": "numeric", "format": _fixed(2)},
            {"name": "Mom 20d %", "id": "momentum20", "type": "numeric", "format": _fixed(2)},
            {"name": "Vol (ann) %", "id": "vol", "type": "numeric", "format": _fixed(1)},
            {"name": "Max DD %", "id": "maxdd", "type": "numeric", "format": _fixed(1)},
            {"name": "RSI", "id": "rsi", "type": "numeric", "format": _fixed(1)},
            {"name": "Sharpe", "id": "sharpe", "type": "numeric", "format": _fixed(2)},
        ],
        data=[{
            "coin_id": coin["coin_id"],
            "price_usd": coin["price_usd"],
            "perf24": coin["performance_percent"].get("24h"),
            "perf7": coin["performance_percent"].get("7d"),
            "perf30": coin["performance_percent"].get("30d"),
            "momentum20": coin["momentum_20d_percent"],
            "vol": coin["volatility_annualized_percent"],
            "maxdd": coin["max_drawdown_percent"],
            "rsi": coin["rsi_14"],
            "sharpe": coin["sharpe"],
        } for coin in coins],
        conditional=(
            [{"if": {"column_id": column, "filter_query": f"{{{column}}} > 0"}, "color": TOKENS["positive"]}
             for column in ("perf24", "perf7", "perf30", "momentum20")]
            + [{"if": {"column_id": column, "filter_query": f"{{{column}}} < 0"}, "color": TOKENS["negative"]}
               for column in ("perf24", "perf7", "perf30", "momentum20")]
            + [{"if": {"column_id": "coin_id"}, "fontWeight": "700"}]
        ),
    )

    correlation_fig = empty
    matrix = comparison.get("correlation_matrix") or {}
    if matrix:
        order = [coin["coin_id"] for coin in coins]
        frame = pd.DataFrame.from_dict(matrix)
        frame = frame[[column for column in order if column in frame.columns]]
        correlation_fig = px.imshow(
            frame, x=frame.columns, y=frame.index, text_auto=".2f",
            color_continuous_scale="RdBu_r", zmin=-1, zmax=1,
        )
        correlation_fig = apply_theme(correlation_fig, height=360, coloraxis_showscale=False)

    normalized_fig = empty
    normalized = (comparison.get("series") or {}).get("normalized_performance") or {}
    if normalized:
        normalized_fig = go.Figure()
        for coin, points in normalized.items():
            frame = pd.DataFrame(points)
            frame["timestamp"] = pd.to_datetime(frame["timestamp"])
            normalized_fig.add_trace(go.Scatter(x=frame["timestamp"], y=frame["value"] * 100,
                                                mode="lines", name=coin, line=dict(width=2.5)))
        normalized_fig = apply_theme(normalized_fig, height=360, yaxis_title="Indexed (start = 100)")

    return leaderboard, correlation_fig, normalized_fig


# ---------------------------------------------------------------- analysis

@app.callback(
    Output("analysis-header", "children"),
    Output("strategy-header", "children"),
    Output("explain-header", "children"),
    Output("intel-header", "children"),
    Input("data-store", "data"),
    Input("active-coin", "data"),
)
def update_asset_headers(store: dict, active_coin: str):
    store = store or {}
    active_coin = active_coin or DEFAULT_COIN
    comparison = store.get("comparison") or {}
    coin = next((item for item in comparison.get("coins") or [] if item["coin_id"] == active_coin), None)
    perf = (coin or {}).get("performance_percent") or {}
    change = perf.get("24h")
    change_class = "text-positive" if (change or 0) > 0 else "text-negative" if (change or 0) < 0 else "text-secondary"

    snapshots = store.get("snapshots") or []
    label = active_coin.replace("-", " ").title()
    if snapshots:
        frame = pd.DataFrame(snapshots)
        row = frame[frame["coin_id"] == active_coin].sort_values("captured_at", ascending=False)
        if not row.empty:
            latest = row.iloc[0]
            label = f"{latest['name']} ({latest['symbol'].upper()})"

    header = html.Div(
        className="card",
        style={"display": "flex", "align-items": "center", "gap": "16px", "flex-wrap": "wrap"},
        children=[
            html.Div([
                html.Div(label, style={"font-size": "18px", "font-weight": 700}),
                html.Div(active_coin, style={"color": TOKENS["text_faint"], "font-size": "11px",
                                             "letter-spacing": ".08em", "text-transform": "uppercase"}),
            ]),
            html.Div([
                html.Div("Price", className="stat-label"),
                html.Div(price_format((coin or {}).get("price_usd")), className="stat-value"),
            ]),
            html.Div([
                html.Div("24h", className="stat-label"),
                html.Div(fmt_pct(change) if change is not None else "—",
                         className="stat-value", style={"color": TOKENS["text"]}),
            ], className=change_class),
            html.Div([
                html.Div("7d", className="stat-label"),
                html.Div(fmt_pct(perf.get("7d")) if perf.get("7d") is not None else "—", className="stat-value"),
            ], className="text-positive" if (perf.get("7d") or 0) > 0 else "text-negative" if (perf.get("7d") or 0) < 0 else "text-secondary"),
            html.Div([
                html.Div("RSI (14)", className="stat-label"),
                html.Div(f"{coin['rsi_14']:.1f}" if (coin or {}).get("rsi_14") is not None else "—", className="stat-value"),
            ]),
        ],
    )
    return header, header, header, header


@app.callback(
    Output("price-chart", "figure"),
    Output("candle-chart", "figure"),
    Output("forecast-chart", "figure"),
    Input("data-store", "data"),
)
def update_charts(store: dict):
    store = store or {}
    analysis = store.get("analysis")
    empty = empty_figure(380)
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
                                   line=dict(color=PALETTE[2], width=2)))
    price_fig.add_trace(go.Scatter(x=series["timestamp"], y=series["sma_30"], name="SMA 30",
                                   line=dict(color=PALETTE[3], width=2)))
    price_fig.add_trace(go.Scatter(x=series["timestamp"], y=series["bollinger_upper"], name="Bollinger upper",
                                   line=dict(color=PALETTE[4], width=1, dash="dot")))
    price_fig.add_trace(go.Scatter(x=series["timestamp"], y=series["bollinger_lower"], name="Bollinger lower",
                                   line=dict(color=PALETTE[4], width=1, dash="dot"),
                                   fill="tonexty", fillcolor="rgba(176,82,107,.08)"))
    price_fig = apply_theme(price_fig, height=380, yaxis_title="USD")

    candle_fig = go.Figure()
    candle_fig.add_trace(go.Candlestick(
        x=candles["date"], open=candles["open"], high=candles["high"], low=candles["low"],
        close=candles["close"], name="OHLC",
        increasing_line_color=TOKENS["positive"], decreasing_line_color=TOKENS["negative"],
    ))
    candle_fig.add_trace(go.Bar(x=candles["date"], y=candles["volume_usd"], name="Volume",
                                marker_color="rgba(31,59,91,.35)", yaxis="y2"))
    candle_fig = apply_theme(
        candle_fig, height=380, yaxis_title="USD",
        yaxis2=dict(title="Volume", overlaying="y", side="right", showgrid=False,
                    gridcolor=TOKENS["grid"], zeroline=False),
        xaxis_rangeslider_visible=False,
    )

    forecast_fig = go.Figure()
    forecast_fig.add_trace(go.Scatter(x=series["timestamp"], y=series["price_usd"], name="Actual",
                                      line=dict(color=PALETTE[0], width=3)))
    forecast_fig.add_trace(go.Scatter(x=forecast["timestamp"], y=forecast["upper_95"], name="95% upper",
                                      line=dict(color="rgba(31,59,91,.3)", width=1), showlegend=False))
    forecast_fig.add_trace(go.Scatter(x=forecast["timestamp"], y=forecast["lower_95"],
                                      name="95% prediction interval",
                                      line=dict(color="rgba(31,59,91,.3)", width=1),
                                      fill="tonexty", fillcolor="rgba(31,59,91,.10)"))
    forecast_fig.add_trace(go.Scatter(x=forecast["timestamp"], y=forecast["price_usd"],
                                      name=f"{analysis['metrics']['selected_model']} forecast",
                                      line=dict(color=PALETTE[3], width=3, dash="dash")))
    forecast_fig.add_trace(go.Scatter(x=series["timestamp"], y=series["rsi_14"], name="RSI 14",
                                      line=dict(color=PALETTE[4]), yaxis="y2"))
    forecast_fig.add_hline(y=70, line_color=TOKENS["negative"], line_dash="dot", yref="y2")
    forecast_fig.add_hline(y=30, line_color=TOKENS["positive"], line_dash="dot", yref="y2")
    forecast_fig = apply_theme(
        forecast_fig, height=350, yaxis_title="USD",
        yaxis2=dict(title="RSI", range=[0, 100], overlaying="y", side="right", showgrid=False),
    )

    return price_fig, candle_fig, forecast_fig


@app.callback(
    Output("model-table", "children"),
    Input("data-store", "data"),
)
def update_model_table(store: dict):
    store = store or {}
    analysis = store.get("analysis")
    if not analysis:
        return html.Div("Choose 90 or 365 days to collect enough observations for rolling model evaluation.",
                        className="note")
    comparison = analysis.get("model_comparison") or []
    if not comparison:
        return html.Div("Choose 90 or 365 days to collect enough observations for rolling model evaluation.",
                        className="note")
    return base_table(
        columns=[
            {"name": "Model", "id": "model"},
            {"name": "MAE", "id": "mae"},
            {"name": "RMSE", "id": "rmse"},
            {"name": "Folds", "id": "folds"},
        ],
        data=comparison,
    )


@app.callback(
    Output("assistant-box", "children"),
    Input("data-store", "data"),
)
def update_assistant(store: dict):
    store = store or {}
    analysis = store.get("analysis")
    if not analysis:
        note = store.get("analysis_error") or "Loading analysis…"
        return html.Div(f"Historical analysis is temporarily unavailable: {note}",
                        style={"color": TOKENS["negative"]})

    metrics = analysis["metrics"]
    summary = store.get("summary") or ""
    assistant = [
        html.P(summary, style={"font-size": ".95rem", "margin": "0 0 12px"}),
        html.Div(className="strip", children=[
            stat_card("Trend", metrics["trend"].title()),
            stat_card("RSI (14)", f"{metrics['rsi_14']:.1f}", metrics["rsi_state"],
                      tone="warning" if metrics["rsi_14"] >= 70 or metrics["rsi_14"] <= 30 else None),
            stat_card("Volatility", f"{metrics['volatility_percent']:.2f}%"),
            stat_card("Fear & Greed", f"{metrics['fear_greed']:.0f}"),
        ]),
        html.P(
            f"VWAP: {price_format(metrics['vwap'])} · Bollinger: {metrics['bollinger_state']} · "
            f"ADF p-value after differencing: {metrics['adf_pvalue'] if metrics['adf_pvalue'] is not None else 'N/A'}",
            className="note",
        ),
    ]
    return assistant


# ---------------------------------------------------------------- strategy

@app.callback(
    Output("backtest-table", "children"),
    Output("backtest-equity-chart", "figure"),
    Input("data-store", "data"),
)
def update_backtest(store: dict):
    store = store or {}
    empty = empty_figure(340)
    backtest = store.get("backtest") or {}
    results = backtest.get("results") or []
    if not results:
        return (html.Div("Not enough history for a meaningful backtest.", className="note"), empty)

    table = base_table(
        columns=[
            {"name": "Strategy", "id": "strategy"},
            {"name": "Return %", "id": "total_return_percent", "type": "numeric", "format": _fixed(2)},
            {"name": "Annualized %", "id": "annualized_return_percent", "type": "numeric", "format": _fixed(2)},
            {"name": "Sharpe", "id": "sharpe", "type": "numeric", "format": _fixed(2)},
            {"name": "Max DD %", "id": "max_drawdown_percent", "type": "numeric", "format": _fixed(1)},
            {"name": "Win rate %", "id": "win_rate_percent", "type": "numeric", "format": _fixed(1)},
            {"name": "Trades", "id": "num_trades", "type": "numeric"},
        ],
        data=results,
        conditional=[
            {"if": {"column_id": "total_return_percent", "filter_query": "{total_return_percent} > 0"},
             "color": TOKENS["positive"]},
            {"if": {"column_id": "total_return_percent", "filter_query": "{total_return_percent} < 0"},
             "color": TOKENS["negative"]},
            {"if": {"column_id": "strategy"}, "fontWeight": "700"},
        ],
    )

    equity_fig = empty
    curves = backtest.get("equity_curves") or {}
    if curves:
        equity_fig = go.Figure()
        for label, points in curves.items():
            frame = pd.DataFrame(points)
            frame["timestamp"] = pd.to_datetime(frame["timestamp"])
            equity_fig.add_trace(go.Scatter(x=frame["timestamp"], y=frame["equity"],
                                            mode="lines", name=label, line=dict(width=2)))
        equity_fig = apply_theme(equity_fig, height=340, yaxis_title="Equity (start = 1.0)")

    return table, equity_fig


# ---------------------------------------------------------------- explainability

@app.callback(
    Output("local-explanation", "children"),
    Output("shap-global-chart", "figure"),
    Output("importance-chart", "figure"),
    Output("signals-chart", "figure"),
    Input("data-store", "data"),
)
def update_explainability(store: dict):
    store = store or {}
    analysis = store.get("analysis") or {}
    empty = empty_figure(300)

    explanation = analysis.get("explanation") or {}
    local_children = []
    local = explanation.get("local") or {}
    contributions = local.get("contributions") or []
    if contributions:
        top = sorted(contributions, key=lambda item: abs(item.get("contribution", 0)), reverse=True)[:8]
        max_abs = max(abs(item.get("contribution", 0)) for item in top) or 1.0
        for item in top:
            contribution = item.get("contribution", 0)
            color = TOKENS["positive"] if contribution >= 0 else TOKENS["negative"]
            width = max(2.0, abs(contribution) / max_abs * 100)
            local_children.append(html.Div(
                style={"display": "flex", "align-items": "center", "gap": ".75rem", "margin": ".3rem 0"},
                children=[
                    html.Div(item.get("feature", ""), style={"flex": "1", "font-size": ".85rem", "font-weight": 600}),
                    html.Div(style={"flex": "2"},
                             children=[html.Div(style={"background": color, "border-radius": "4px",
                                                       "height": "10px", "width": f"{width:.0f}%"})]),
                    html.Div(f"{contribution:+.5f}", style={"width": "84px", "text-align": "right",
                                                           "font-size": ".8rem", "color": color}),
                ],
            ))
        local_children.append(html.Small(
            f"SHAP contribution to the next-day return forecast ({local.get('method', '')}).",
            className="note"))
    else:
        local_children = [html.Div("Explanation unavailable for this model or history window.", className="note")]

    shap_fig = empty
    global_importance_data = explanation.get("global") or {}
    features = global_importance_data.get("features") or []
    if features:
        frame = pd.DataFrame(features).sort_values("importance")
        shap_fig = px.bar(frame, x="importance", y="feature", orientation="h",
                          color="importance", color_continuous_scale="Blues",
                          labels={"importance": "Mean |SHAP|", "feature": "Feature"})
        shap_fig = apply_theme(shap_fig, height=300, yaxis=dict(autorange="reversed"),
                               coloraxis_showscale=False)

    importance_fig = empty
    importance = analysis.get("feature_importance") or []
    if importance:
        frame = pd.DataFrame(importance)
        importance_fig = px.bar(frame, x="importance", y="feature", orientation="h",
                                color="importance", color_continuous_scale="Blues",
                                labels={"importance": "Gain importance", "feature": "Feature"})
        importance_fig = apply_theme(importance_fig, height=300,
                                     yaxis=dict(autorange="reversed"), coloraxis_showscale=False)

    signals_fig = empty
    signals = analysis.get("signals") or []
    if signals:
        frame = pd.DataFrame(signals)
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        signals_fig = px.bar(frame, x="timestamp", y="actual_return", color="signal",
                             color_discrete_map={"BUY": TOKENS["positive"], "HOLD": TOKENS["warning"]},
                             labels={"actual_return": "Next-period return", "timestamp": "Time"})
        signals_fig = apply_theme(signals_fig, height=280)

    return local_children, shap_fig, importance_fig, signals_fig


# ---------------------------------------------------------------- intelligence

@app.callback(
    Output("alerts-table", "children"),
    Output("drift-status", "children"),
    Output("quality-box", "children"),
    Input("data-store", "data"),
    Input("alert-filter", "value"),
)
def update_intelligence(store: dict, severity: str):
    store = store or {}
    severity = severity or "all"

    alerts = store.get("alerts") or []
    if store.get("alerts_error"):
        alerts_children = [html.Div(f"Alerts unavailable: {store['alerts_error']}",
                                    style={"color": TOKENS["negative"]})]
    else:
        filtered = [a for a in alerts if severity == "all" or str(a.get("severity") or "").lower() == severity]
        if not filtered:
            alerts_children = [html.Div("No alerts match this filter.", className="note")]
        else:
            alerts_children = [
                base_table(
                    columns=[
                        {"name": "Time", "id": "created_at"},
                        {"name": "Severity", "id": "severity"},
                        {"name": "Asset", "id": "coin_id"},
                        {"name": "Message", "id": "message"},
                        {"name": "24h %", "id": "change", "type": "numeric", "format": _fixed(2)},
                    ],
                    data=[{
                        "created_at": (a.get("created_at") or "")[:19].replace("T", " "),
                        "severity": (a.get("severity") or "").upper(),
                        "coin_id": a.get("coin_id") or "",
                        "message": a.get("message") or "",
                        "change": a.get("change_24h_percent"),
                    } for a in filtered],
                    conditional=[
                        {"if": {"column_id": "severity", "filter_query": "{severity} = 'HIGH'"}, "color": TOKENS["negative"]},
                        {"if": {"column_id": "severity", "filter_query": "{severity} = 'MEDIUM'"}, "color": TOKENS["warning"]},
                        {"if": {"column_id": "change", "filter_query": "{change} > 0"}, "color": TOKENS["positive"]},
                        {"if": {"column_id": "change", "filter_query": "{change} < 0"}, "color": TOKENS["negative"]},
                    ],
                )
            ]

    drift = store.get("drift") or {}
    if drift:
        if drift.get("drifted"):
            drift_status = insight_card("DRIFT DETECTED", [
                html.Div(drift.get("detail") or "Model input distribution changed materially.",
                         style={"color": TOKENS["negative"]}),
            ])
        elif drift.get("status") == "insufficient data":
            drift_status = insight_card("TRACKING", [
                html.Div(drift.get("detail") or "Not enough history to evaluate drift yet.",
                         style={"color": TOKENS["text_secondary"]}),
            ])
        else:
            drift_status = insight_card("HEALTHY", [
                html.Div(drift.get("detail") or "No material drift detected.",
                         style={"color": TOKENS["positive"]}),
            ])
    else:
        drift_status = html.Div("No drift evaluation available yet.", className="note")

    quality = store.get("data_quality") or {}
    if quality:
        checks = quality.get("checks") or []
        rows = [html.Div(
            [
                html.Span(check.get("check", "").replace("_", " ").title(),
                          style={"flex": "1", "font-size": "12px", "font-weight": 600}),
                pill(str(check.get("status") or "?").upper(),
                     "positive" if check.get("status") == "OK"
                     else "warning" if check.get("status") == "WARN" else "negative"),
                html.Div(check.get("detail") or "", style={"flex": "2", "font-size": "11px",
                                                           "color": TOKENS["text_secondary"]}),
            ],
            style={"display": "flex", "align-items": "center", "gap": "8px", "padding": "5px 0",
                   "border-bottom": f"1px solid {TOKENS['border']}"},
        ) for check in checks]
        if quality.get("issues"):
            rows.append(html.Div([html.B("Issues: "), " ".join(quality["issues"])],
                                 style={"color": TOKENS["warning"], "font-size": "12px", "margin-top": "8px"}))
        quality_children = rows
    else:
        quality_children = [html.Div("No data-quality evaluation yet.", className="note")]

    return alerts_children, drift_status, quality_children


# ---------------------------------------------------------------- system

def _read_model_runs(coin_id: str, limit: int = 8) -> list[dict]:
    if not MODEL_RUNS_FILE.exists():
        return []
    runs = []
    try:
        with MODEL_RUNS_FILE.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if record.get("coin_id") == coin_id:
                    runs.append(record)
    except OSError:
        return []
    return runs[-limit:][::-1]


@app.callback(
    Output("quality-box-system", "children"),
    Output("model-runs", "children"),
    Output("sidebar-status", "children"),
    Input("data-store", "data"),
    Input("active-coin", "data"),
)
def update_system(store: dict, active_coin: str):
    store = store or {}
    active_coin = active_coin or DEFAULT_COIN

    quality_children = []
    snapshots = store.get("snapshots") or []
    if snapshots:
        frame = pd.DataFrame(snapshots)
        newest = pd.to_datetime(frame["captured_at"], utc=True).max().to_pydatetime()
        age_minutes = (datetime.now(timezone.utc) - newest).total_seconds() / 60
        quality_children = html.Div(className="strip", children=[
            stat_card("Stored snapshots", f"{len(frame):,}"),
            stat_card("Tracked coins", f"{frame['coin_id'].nunique()}"),
            stat_card("Last refresh", f"{age_minutes:.0f} min ago"),
            stat_card("API", str(store.get("api_health") or "unknown").upper(),
                      tone="positive" if store.get("api_health") == "ok" else "negative"),
        ])
    else:
        quality_children = html.Div("No data yet — click Refresh market data.", className="note")

    runs = _read_model_runs(active_coin)
    if runs:
        model_runs_children = base_table(
            columns=[
                {"name": "Run at", "id": "run_at"},
                {"name": "Model", "id": "selected_model"},
                {"name": "MAE", "id": "mae", "type": "numeric", "format": _fixed(1)},
                {"name": "RMSE", "id": "rmse", "type": "numeric", "format": _fixed(1)},
                {"name": "Dir acc %", "id": "directional_accuracy", "type": "numeric", "format": _fixed(2)},
                {"name": "Days", "id": "history_days", "type": "numeric"},
                {"name": "Features", "id": "feature_count", "type": "numeric"},
            ],
            data=[{
                "run_at": (r.get("run_at") or "")[:19].replace("T", " "),
                "selected_model": r.get("selected_model") or "",
                "mae": r.get("mae"),
                "rmse": r.get("rmse"),
                "directional_accuracy": r.get("directional_accuracy"),
                "history_days": r.get("history_days"),
                "feature_count": r.get("feature_count"),
            } for r in runs],
        )
    else:
        model_runs_children = html.Div(f"No recorded runs for {active_coin} yet — open Forecast Lab to run an analysis.",
                                       className="note")

    api_tone = "positive" if store.get("api_health") == "ok" else "negative"
    sidebar_status = html.Div([
        html.Div(className="status-row", children=[
            html.Span(className="live-dot"),
            html.Span(f"API {store.get('api_health') or 'unknown'}", style={"color": TOKENS["text_secondary"]}),
        ]),
        html.Div(className="status-row", children=[
            html.Span(f"Asset: {active_coin.upper()}", style={"color": TOKENS["text_secondary"]}),
        ]),
        html.Div(className="status-row", children=[
            html.Span(f"Snapshot count: {len(snapshots):,}", style={"color": TOKENS["text_faint"]}),
        ]),
    ])
    return quality_children, model_runs_children, sidebar_status


# ---------------------------------------------------------------- risk

@app.callback(
    Output("risk-header", "children"),
    Output("risk-stats", "children"),
    Output("drawdown-chart", "figure"),
    Output("var-panel", "children"),
    Input("data-store", "data"),
    Input("active-coin", "data"),
)
def update_risk(store: dict, active_coin: str):
    store = store or {}
    active_coin = active_coin or DEFAULT_COIN
    risk = store.get("risk") or {}
    comparison = store.get("comparison") or {}
    coin = next((item for item in comparison.get("coins") or [] if item["coin_id"] == active_coin), None)
    perf = (coin or {}).get("performance_percent") or {}
    change = perf.get("24h")
    change_class = "text-positive" if (change or 0) > 0 else "text-negative" if (change or 0) < 0 else "text-secondary"

    snapshots = store.get("snapshots") or []
    label = active_coin.replace("-", " ").title()
    if snapshots:
        frame = pd.DataFrame(snapshots)
        row = frame[frame["coin_id"] == active_coin].sort_values("captured_at", ascending=False)
        if not row.empty:
            latest = row.iloc[0]
            label = f"{latest['name']} ({latest['symbol'].upper()})"

    vol_ann = (risk.get("volatility_percent") or {}).get("annualized")
    mdd = risk.get("max_drawdown_percent")
    header = html.Div(
        className="card",
        style={"display": "flex", "align-items": "center", "gap": "16px", "flex-wrap": "wrap"},
        children=[
            html.Div([
                html.Div(label, style={"font-size": "18px", "font-weight": 700}),
                html.Div(active_coin, style={"color": TOKENS["text_faint"], "font-size": "11px",
                                             "letter-spacing": ".08em", "text-transform": "uppercase"}),
            ]),
            html.Div([
                html.Div("Price", className="stat-label"),
                html.Div(price_format((coin or {}).get("price_usd")), className="stat-value"),
            ]),
            html.Div([
                html.Div("24h", className="stat-label"),
                html.Div(fmt_pct(change) if change is not None else "—", className="stat-value"),
            ], className=change_class),
            html.Div([
                html.Div("Vol (ann)", className="stat-label"),
                html.Div(f"{vol_ann:.1f}%" if vol_ann is not None else "—", className="stat-value"),
            ]),
            html.Div([
                html.Div("Max DD", className="stat-label"),
                html.Div(f"{mdd:.1f}%" if mdd is not None else "—", className="stat-value"),
            ]),
        ],
    )

    if not risk:
        stats = [html.Div("Risk metrics appear once 90 days of history are available.", className="note")]
        var_panel = html.Div("Value at risk is estimated from the 90-day return distribution.", className="note")
    else:
        ratios = risk.get("ratios") or {}
        var = risk.get("var") or {}
        stats = [
            stat_card("Volatility (ann)", f"{vol_ann:.1f}%" if vol_ann is not None else "—"),
            stat_card("Max drawdown", f"{mdd:.1f}%" if mdd is not None else "—",
                      tone="negative" if (mdd or 0) < -25 else "warning"),
            stat_card("Sharpe", f"{ratios['sharpe']:.2f}" if ratios.get("sharpe") is not None else "—"),
            stat_card("Sortino", f"{ratios['sortino']:.2f}" if ratios.get("sortino") is not None else "—"),
            stat_card("Calmar", f"{ratios['calmar']:.2f}" if ratios.get("calmar") is not None else "—"),
            stat_card("VaR 95% (1d)", f"{var['historical_var_percent']:.2f}%"
                      if var.get("historical_var_percent") is not None else "—"),
            stat_card("CVaR 95%", f"{var['cvar_percent']:.2f}%"
                      if var.get("cvar_percent") is not None else "—"),
        ]
        if var.get("interpretation"):
            stats.append(html.Div(var["interpretation"], className="note", style={"margin-left": "4px"}))
        var_panel = html.Div(children=[
            html.Div(className="strip", children=[
                stat_card("Historical VaR", f"{var['historical_var_percent']:.2f}%"
                          if var.get("historical_var_percent") is not None else "—", tone="negative"),
                stat_card("Parametric VaR", f"{var['parametric_var_percent']:.2f}%"
                          if var.get("parametric_var_percent") is not None else "—", tone="negative"),
                stat_card("CVaR / Expected Shortfall", f"{var['cvar_percent']:.2f}%"
                          if var.get("cvar_percent") is not None else "—", tone="warning"),
            ]),
            html.P(var.get("interpretation") or "", className="note", style={"margin-top": "12px"}),
        ])

    drawdown_fig = empty_figure(300)
    drawdown_series = risk.get("drawdown_series") or []
    if drawdown_series:
        frame = pd.DataFrame(drawdown_series)
        try:
            day_numbers = frame["timestamp"].astype(int)
            today = pd.Timestamp.now(tz="UTC").normalize()
            frame["timestamp"] = today - pd.to_timedelta(day_numbers.max() - day_numbers, unit="D")
        except (ValueError, TypeError):
            frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        drawdown_fig = go.Figure()
        drawdown_fig.add_trace(go.Scatter(
            x=frame["timestamp"], y=frame["drawdown"] * 100, name="Drawdown",
            line=dict(color=TOKENS["negative"], width=1.8), fill="tozeroy",
            fillcolor="rgba(217,75,75,.06)",
        ))
        drawdown_fig = apply_theme(drawdown_fig, height=300, yaxis_title="% from peak")
        drawdown_fig.update_yaxes(ticksuffix="%")

    return header, stats, drawdown_fig, var_panel


# ---------------------------------------------------------------- homepage

@app.callback(
    Output("home-hero-btc-price", "children"),
    Output("home-hero-btc-change", "children"),
    Output("home-hero-btc-change", "className"),
    Output("home-hero-eth-price", "children"),
    Output("home-hero-eth-change", "children"),
    Output("home-hero-eth-change", "className"),
    Output("home-hero-sentiment-value", "children"),
    Output("home-hero-sentiment-label", "children"),
    Output("home-hero-gauge-fill", "style"),
    Output("home-hero-volatility", "children"),
    Output("home-hero-spark", "children"),
    Input("data-store", "data"),
)
def home_hero_live(store: dict):
    store = store or {}
    comparison = store.get("comparison") or {}
    coins = comparison.get("coins") or []
    btc = next((item for item in coins if item["coin_id"] == "bitcoin"), None)
    eth = next((item for item in coins if item["coin_id"] == "ethereum"), None)
    if not coins:
        return [no_update] * 11

    def change_value(coin):
        change = ((coin or {}).get("performance_percent") or {}).get("24h")
        if change is None:
            return "—", "hero-card-change text-secondary"
        cls = ("hero-card-change text-positive" if change > 0
               else "hero-card-change text-negative" if change < 0 else "hero-card-change text-secondary")
        return f"{fmt_pct(change)} / 24h", cls

    btc_price = price_format(btc.get("price_usd")) if btc else "—"
    eth_price = price_format(eth.get("price_usd")) if eth else "—"
    btc_change, btc_cls = change_value(btc)
    eth_change, eth_cls = change_value(eth)

    sentiment_value, sentiment_label, gauge_style = no_update, no_update, no_update
    overview = store.get("overview") or {}
    fear_greed = overview.get("fear_greed") or {}
    if fear_greed.get("value") is not None:
        sentiment_value = f"{fear_greed['value']:.0f}"
        sentiment_label = (fear_greed.get("label") or "NEUTRAL").upper()
        gauge_style = {"width": f"{fear_greed['value']:.0f}%"}

    volatility = no_update
    risk = store.get("risk") or {}
    vol_ann = (risk.get("volatility_percent") or {}).get("annualized")
    if vol_ann is None and btc and btc.get("volatility_annualized_percent") is not None:
        vol_ann = btc["volatility_annualized_percent"]
    if vol_ann is not None:
        volatility = f"{vol_ann:.1f}%"

    normalized = (comparison.get("series") or {}).get("normalized_performance") or {}
    points = normalized.get("bitcoin") or normalized.get("ethereum") or []
    if points:
        spark = home._sparkline_svg([point["value"] * 100 for point in points][-120:], width=265, height=64)
    else:
        spark = home._sparkline_svg([])

    return (btc_price, btc_change, btc_cls, eth_price, eth_change, eth_cls,
            sentiment_value, sentiment_label, gauge_style, volatility, spark)


@app.callback(
    Output("home-market-price-list", "children"),
    Input("data-store", "data"),
)
def home_market_preview(store: dict):
    store = store or {}
    coins = (store.get("comparison") or {}).get("coins") or []
    if not coins:
        return no_update
    rows = []
    for coin in sorted(coins, key=lambda item: (item.get("price_usd") or 0), reverse=True)[:5]:
        change = (coin.get("performance_percent") or {}).get("24h")
        change_cls = ("mini-market-change text-positive" if (change or 0) > 0
                      else "mini-market-change text-negative" if (change or 0) < 0
                      else "mini-market-change text-secondary")
        dot = "hero-dot-eth" if coin["coin_id"] == "ethereum" else "hero-dot-btc"
        rows.append(html.Div(className="mini-market-row", children=[
            html.Div(className="mini-market-symbol", children=[
                html.Span(className=f"hero-dot {dot}"),
                html.Span(coin["coin_id"].replace("-", " ").upper()),
            ]),
            html.Div(price_format(coin.get("price_usd")), className="mini-market-price"),
            html.Div(fmt_pct(change) if change is not None else "—", className=change_cls),
        ]))
    return rows


@app.callback(
    Output("home-risk-chips", "children"),
    Input("data-store", "data"),
)
def home_risk_chips(store: dict):
    store = store or {}
    risk = store.get("risk") or {}
    if not risk:
        return no_update
    chips = []
    vol_ann = (risk.get("volatility_percent") or {}).get("annualized")
    if vol_ann is not None:
        chips.append(html.Span(f"VOLATILITY {vol_ann:.1f}%", className="chip chip-stat"))
    mdd = risk.get("max_drawdown_percent")
    if mdd is not None:
        chips.append(html.Span(f"MAX DD {mdd:.1f}%", className="chip chip-stat"))
    sharpe = (risk.get("ratios") or {}).get("sharpe")
    if sharpe is not None:
        chips.append(html.Span(f"SHARPE {sharpe:.2f}", className="chip chip-stat"))
    cvar = (risk.get("var") or {}).get("cvar_percent")
    if cvar is not None:
        chips.append(html.Span(f"CVaR {cvar:.1f}%", className="chip chip-stat"))
    return chips or no_update


@app.callback(
    Output("home-intel-score", "children"),
    Output("home-intel-label", "children"),
    Output("home-intel-factors", "children"),
    Input("data-store", "data"),
)
def home_intel_score(store: dict):
    store = store or {}
    score = store.get("score") or {}
    if not score or score.get("score") is None:
        return no_update, no_update, no_update
    factors = []
    for component in score.get("components") or []:
        if (component.get("points") or 0) >= 0:
            factors.append(html.Span(f"{component.get('name')} +", className="factor factor-pos"))
        else:
            factors.append(html.Span(f"{component.get('name')} −", className="factor factor-neg"))
    if not factors:
        factors = [html.Span("Score available", className="factor factor-pos")]
    return f"{score['score']:.0f}", (score.get("label") or "NEUTRAL").upper(), factors


@app.callback(
    Output("home-alert-list", "children"),
    Input("data-store", "data"),
)
def home_alert_list(store: dict):
    store = store or {}
    alerts = store.get("alerts") or []
    if store.get("alerts_error"):
        return [html.Div(f"Alerts unavailable: {store['alerts_error']}", className="mini-alert-empty")]
    if not alerts:
        return [html.Div("No significant movement or technical alerts recorded yet.", className="mini-alert-empty")]
    colors = {"high": TOKENS["negative"], "medium": TOKENS["warning"], "low": TOKENS["text_secondary"]}
    items = []
    for alert in alerts[:3]:
        severity = (alert.get("severity") or "low").lower()
        color = colors.get(severity, TOKENS["text_secondary"])
        items.append(html.Div(className="mini-alert-item", children=[
            html.Span((alert.get("severity") or "?").upper(), className="mini-alert-sev",
                      style={"background": f"{color}1A", "color": color}),
            html.Span(f"{alert.get('coin_id', '').replace('-', ' ').upper()} · {alert.get('message', '')}",
                      style={"flex": "1"}),
        ]))
    return items


@app.callback(
    Output("home-news-cards", "children"),
    Input("data-store", "data"),
)
def update_home_news(store: dict):
    return _asset_news_cards(store, active_coin=None)


# ---------------------------------------------------------------- downloads

@app.callback(
    Output("download-analysis", "data"),
    Input("download-analysis-button", "n_clicks"),
    State("data-store", "data"),
    State("active-coin", "data"),
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
    State("active-coin", "data"),
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
