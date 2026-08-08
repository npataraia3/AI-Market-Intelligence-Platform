"""Design system for the market research workstation.

Single source of truth for colour, typography, spacing and the Plotly
chart language. Light mode is the default; dark tokens are provided so a
``data-theme="dark"`` swap on the root element is a supported, one-line
change without touching component code.
"""

from __future__ import annotations

import plotly.graph_objects as go

FONT_STACK = "Segoe UI, -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif"

LIGHT = {
    "background": "#F6F7F5",
    "surface": "#FFFFFF",
    "surface_alt": "#FBFCFA",
    "border": "#E4E7E2",
    "border_strong": "#D3D8D2",
    "text": "#151817",
    "text_secondary": "#6B726E",
    "text_faint": "#9AA29D",
    "accent": "#1F3B5B",          # dark navy
    "accent_2": "#3976D2",        # info blue
    "positive": "#198754",
    "negative": "#D94B4B",
    "warning": "#C68A18",
    "neutral": "#6B7280",
    "grid": "#EDF0EC",
    "chart_palette": ["#1F3B5B", "#3976D2", "#2E9E6B", "#C68A18", "#B0526B"],
    "sidebar_bg": "#FFFFFF",
    "topbar_bg": "#FFFFFF",
    "positive_bg": "rgba(25,135,84,.08)",
    "negative_bg": "rgba(217,75,75,.08)",
    "warning_bg": "rgba(198,138,24,.10)",
    "accent_bg": "rgba(31,59,91,.06)",
}

DARK = {
    "background": "#14161A",
    "surface": "#1C1F24",
    "surface_alt": "#22262C",
    "border": "#2C3138",
    "border_strong": "#3A4048",
    "text": "#EDEFEC",
    "text_secondary": "#9AA29D",
    "text_faint": "#6B726E",
    "accent": "#7FA6D9",
    "accent_2": "#5B93E0",
    "positive": "#3DB97F",
    "negative": "#E06A6A",
    "warning": "#D9A441",
    "neutral": "#8B929B",
    "grid": "#2A2F36",
    "chart_palette": ["#7FA6D9", "#5B93E0", "#3DB97F", "#D9A441", "#D98CA0"],
    "sidebar_bg": "#1C1F24",
    "topbar_bg": "#1C1F24",
    "positive_bg": "rgba(61,185,127,.12)",
    "negative_bg": "rgba(224,106,106,.12)",
    "warning_bg": "rgba(217,164,65,.14)",
    "accent_bg": "rgba(127,166,217,.10)",
}

TOKENS = LIGHT  # active theme — flip to DARK to switch the whole shell


def css(active: dict | None = None) -> str:
    t = active or TOKENS
    return f"""
:root {{
    --background: {t["background"]};
    --surface: {t["surface"]};
    --surface-alt: {t["surface_alt"]};
    --border: {t["border"]};
    --border-strong: {t["border_strong"]};
    --text: {t["text"]};
    --text-secondary: {t["text_secondary"]};
    --text-faint: {t["text_faint"]};
    --accent: {t["accent"]};
    --accent-2: {t["accent_2"]};
    --positive: {t["positive"]};
    --negative: {t["negative"]};
    --warning: {t["warning"]};
    --neutral: {t["neutral"]};
    --sidebar-bg: {t["sidebar_bg"]};
    --topbar-bg: {t["topbar_bg"]};
    --positive-bg: {t["positive_bg"]};
    --negative-bg: {t["negative_bg"]};
    --warning-bg: {t["warning_bg"]};
    --accent-bg: {t["accent_bg"]};
    --font-stack: {FONT_STACK};
}}

* {{ box-sizing: border-box; }}

html, body {{
    background: var(--background);
    color: var(--text);
    font-family: var(--font-stack);
    font-size: 14px;
    line-height: 1.45;
    margin: 0;
}}

.dash-app-shell {{ display: flex; min-height: 100vh; }}

/* ---------- Sidebar ---------- */
.sidebar {{
    width: 232px;
    flex: 0 0 232px;
    background: var(--sidebar-bg);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    position: sticky;
    top: 0;
    height: 100vh;
    overflow-y: auto;
}}
.sidebar-brand {{
    padding: 18px 20px 14px;
    border-bottom: 1px solid var(--border);
}}
.sidebar-brand-title {{
    font-size: 11px;
    font-weight: 700;
    letter-spacing: .14em;
    color: var(--accent);
    text-transform: uppercase;
}}
.sidebar-brand-sub {{
    font-size: 11px;
    color: var(--text-faint);
    letter-spacing: .04em;
    margin-top: 3px;
    text-transform: uppercase;
}}
.sidebar-nav {{ flex: 1; padding: 14px 12px 8px; }}
.nav-section-label {{
    font-size: 10px;
    font-weight: 700;
    letter-spacing: .12em;
    color: var(--text-faint);
    text-transform: uppercase;
    padding: 10px 10px 4px;
}}
.nav-item {{
    display: block;
    padding: 7px 10px;
    margin: 1px 0;
    border-radius: 6px;
    color: var(--text-secondary);
    text-decoration: none;
    font-weight: 600;
    font-size: 13px;
}}
.nav-item:hover {{ background: var(--surface-alt); color: var(--text); }}
.nav-item.active {{ background: var(--accent-bg); color: var(--accent); }}
.sidebar-footer {{
    border-top: 1px solid var(--border);
    padding: 12px 20px;
    font-size: 11px;
    color: var(--text-faint);
}}
.status-row {{ display: flex; align-items: center; gap: 6px; margin: 3px 0; }}

/* ---------- Main column ---------- */
.main {{ flex: 1; min-width: 0; display: flex; flex-direction: column; }}
.topbar {{
    background: var(--topbar-bg);
    border-bottom: 1px solid var(--border);
    padding: 10px 28px;
    display: flex;
    align-items: center;
    gap: 20px;
    position: sticky;
    top: 0;
    z-index: 20;
}}
.topbar-page {{ font-size: 12px; font-weight: 700; letter-spacing: .1em; color: var(--text-secondary); text-transform: uppercase; }}
.topbar-spacer {{ flex: 1; }}
.live-dot {{
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--positive);
    display: inline-block;
    animation: live-pulse 2s ease-in-out infinite;
}}
@keyframes live-pulse {{
    0%, 100% {{ opacity: 1; }}
    50% {{ opacity: .35; }}
}}
.live-label {{ font-size: 11px; font-weight: 700; letter-spacing: .12em; color: var(--text-secondary); text-transform: uppercase; }}
.page {{ max-width: 1600px; width: 100%; margin: 0 auto; padding: 24px 28px 48px; }}
.page-loading-wrap {{ position: relative; }}
.page-loading-wrap .dash-loading {{ background: rgba(244,246,243,.75); }} /* spinner overlay */

/* ---------- Cards & sections ---------- */
.card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px 18px;
    box-shadow: 0 1px 2px rgba(20,24,23,.03);
}}
.card-title {{
    font-size: 11px;
    font-weight: 700;
    letter-spacing: .1em;
    color: var(--text-faint);
    text-transform: uppercase;
    margin: 0 0 10px;
}}
.page-heading {{ margin-bottom: 18px; }}
.page-heading h1 {{ font-size: 20px; font-weight: 700; margin: 0; letter-spacing: -.01em; }}
.page-heading p {{ color: var(--text-secondary); font-size: 13px; margin: 4px 0 0; }}

.stat-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 3px solid var(--border-strong);
    border-radius: 8px;
    padding: 10px 14px;
    min-width: 130px;
}}
.stat-label {{ font-size: 11px; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; letter-spacing: .05em; }}
.stat-value {{ font-size: 19px; font-weight: 700; margin-top: 2px; letter-spacing: -.01em; }}
.stat-sub {{ font-size: 11px; color: var(--text-faint); margin-top: 2px; }}

.help-badge {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 14px; height: 14px;
    border-radius: 50%;
    border: 1px solid var(--border-strong);
    color: var(--text-faint);
    font-size: 10px;
    font-weight: 700;
    cursor: help;
    vertical-align: middle;
    margin-left: 6px;
}}

.pill {{
    display: inline-block;
    font-size: 11px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 999px;
    letter-spacing: .03em;
}}
.pill.positive {{ color: var(--positive); background: var(--positive-bg); }}
.pill.negative {{ color: var(--negative); background: var(--negative-bg); }}
.pill.warning {{ color: var(--warning); background: var(--warning-bg); }}
.pill.neutral {{ color: var(--text-secondary); background: var(--surface-alt); border: 1px solid var(--border); }}
.pill.accent {{ color: var(--accent); background: var(--accent-bg); }}
.pill.info {{ color: var(--accent-2); background: var(--accent-bg); }}

.text-positive {{ color: var(--positive); }}
.text-negative {{ color: var(--negative); }}
.text-warning {{ color: var(--warning); }}
.text-secondary {{ color: var(--text-secondary); }}
.text-faint {{ color: var(--text-faint); }}

.grid-2 {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }}
.grid-3 {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }}
.grid-4 {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; }}
.strip {{ display: flex; flex-wrap: wrap; gap: 12px; }}
@media (max-width: 1100px) {{
    .grid-3, .grid-4 {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
}}

/* ---------- Asset news cards ---------- */
.asset-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 10px;
}}
.asset-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 10px 12px;
    color: var(--text);
    display: flex;
    flex-direction: column;
    gap: 8px;
    transition: border-color .12s, box-shadow .12s;
}}
.asset-card:hover {{ border-color: var(--border-strong); }}
.asset-card.active {{
    border-color: var(--accent);
    background: linear-gradient(180deg, var(--accent-bg), var(--surface) 55%);
    box-shadow: 0 0 0 1px var(--accent);
}}
.asset-card-head {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }}
.asset-id {{ display: flex; align-items: center; gap: 7px; min-width: 0; }}
.asset-glyph {{ font-size: 17px; line-height: 1; color: var(--accent-2); }}
.asset-name-block {{ display: flex; flex-direction: column; min-width: 0; }}
.asset-card-name {{
    font-size: 12px; font-weight: 700; letter-spacing: .06em;
    color: var(--text); text-decoration: none;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}}
.asset-card-name:hover {{ color: var(--accent); }}
.asset-ticker {{ font-size: 10px; color: var(--text-faint); letter-spacing: .04em; }}
.asset-focus-tag {{ font-size: 9px; font-weight: 700; letter-spacing: .1em; color: var(--accent); text-transform: uppercase; }}
.asset-quote {{ text-align: right; flex-shrink: 0; }}
.asset-price-small {{ font-size: 12px; font-weight: 700; letter-spacing: -.01em; }}
.asset-change-small {{ font-size: 10px; font-weight: 600; }}

.asset-news {{ min-height: 78px; display: flex; flex-direction: column; gap: 6px; }}
.asset-news-body {{ display: flex; gap: 9px; align-items: flex-start; min-width: 0; flex: 1; }}
.asset-thumb {{
    flex-shrink: 0;
    width: 60px; height: 60px;
    border-radius: 7px;
    background-size: cover;
    background-position: center;
    background-color: var(--surface-alt);
    border: 1px solid var(--border);
}}
.asset-headline {{
    font-size: 12px; line-height: 1.4; color: var(--text); font-weight: 600;
    text-decoration: none;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
    min-width: 0; flex: 1;
}}
.asset-headline:hover {{ color: var(--accent); }}
.asset-news-foot {{
    display: flex; align-items: center; justify-content: space-between; gap: 8px;
    border-top: 1px dashed var(--border); padding-top: 6px;
}}
.asset-news-source {{
    font-size: 10px; color: var(--text-secondary); text-decoration: none;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}}
.asset-news-source:hover {{ color: var(--accent); }}
.asset-news-analyze {{
    font-size: 10px; font-weight: 700; letter-spacing: .03em;
    color: var(--accent); text-decoration: none; white-space: nowrap;
}}
.asset-news-analyze:hover {{ text-decoration: underline; }}
.asset-news-hint {{ font-size: 11px; color: var(--text-faint); }}
.asset-news-meta {{ font-size: 10px; color: var(--text-faint); margin-top: 3px; }}

.asset-news-loading {{ justify-content: center; }}
.asset-skeleton {{
    height: 10px;
    border-radius: 5px;
    background: linear-gradient(90deg, var(--border) 25%, var(--surface-alt) 50%, var(--border) 75%);
    background-size: 200% 100%;
    animation: asset-shimmer 1.3s ease-in-out infinite;
}}
@keyframes asset-shimmer {{ 0% {{ background-position: 200% 0; }} 100% {{ background-position: -200% 0; }} }}

.asset-news-error {{ justify-content: center; align-items: flex-start; gap: 8px; }}
.asset-retry-btn {{
    border: 1px solid var(--border-strong);
    background: var(--surface);
    color: var(--text);
    border-radius: 6px;
    padding: 4px 12px;
    font-size: 11px;
    font-weight: 700;
    cursor: pointer;
}}
.asset-retry-btn:hover {{ border-color: var(--accent); color: var(--accent); }}


/* ---------- Buttons & controls ---------- */
.btn {{
    border: 1px solid var(--border-strong);
    background: var(--surface);
    color: var(--text);
    border-radius: 8px;
    padding: 7px 14px;
    font-weight: 600;
    font-size: 13px;
    cursor: pointer;
}}
.btn:hover {{ border-color: var(--accent-2); }}
.btn-primary {{
    border: 1px solid var(--accent);
    background: var(--accent);
    color: #fff;
    border-radius: 8px;
    padding: 7px 14px;
    font-weight: 600;
    font-size: 13px;
    cursor: pointer;
}}
.btn-primary:hover {{ opacity: .92; }}

.alert-item {{
    border-left: 3px solid var(--border-strong);
    padding: 8px 10px;
    border-radius: 6px;
    background: var(--surface-alt);
    margin-bottom: 8px;
}}
.alert-item.high {{ border-left-color: var(--negative); }}
.alert-item.medium {{ border-left-color: var(--warning); }}
.alert-item.low {{ border-left-color: var(--accent-2); }}

.note {{ color: var(--text-secondary); font-size: 12px; margin: 6px 0 0; }}

.insight-card {{
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent-2);
    background: var(--surface);
    border-radius: 8px;
    padding: 12px 14px;
    margin-bottom: 10px;
}}
.insight-card .insight-label {{
    font-size: 10px; font-weight: 700; letter-spacing: .1em;
    color: var(--accent-2); text-transform: uppercase; margin-bottom: 4px;
}}

/* ---------- Overrides for Dash/Plotly chrome ---------- */
.dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner td,
.dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner th {{
    font-family: var(--font-stack);
}}
.dash-dropdown {{ border: none; }}
.Select-control {{
    border: 1px solid var(--border-strong) !important;
    border-radius: 8px !important;
    background: var(--surface) !important;
}}
.Select-value-label {{ color: var(--text) !important; }}
.Select-menu-outer {{ border: 1px solid var(--border) !important; border-radius: 8px !important; z-index: 30; }}
.Select-option {{ color: var(--text) !important; }}
.Select-option.is-selected {{ color: var(--accent) !important; }}
.Select-option.is-focused {{ background: var(--accent-bg) !important; }}
.modebar {{ opacity: .5 !important; }}

a {{ color: var(--accent-2); }}
h1, h2, h3, h4 {{ color: var(--text); }}

/* ---------- Homepage landing ---------- */
.home {{ background: var(--background); min-height: 100vh; }}
.home a {{ text-decoration: none; }}

/* Header */
.home-header {{
    position: sticky; top: 0; z-index: 50;
    display: flex; align-items: center; gap: 24px;
    padding: 14px 44px;
    background: rgba(246,247,245,.9);
    backdrop-filter: blur(8px);
    border-bottom: 1px solid var(--border);
}}
.home-brand {{ display: flex; align-items: center; gap: 10px; }}
.home-logo {{ display: inline-flex; }}
.home-logo svg {{ width: 30px; height: 30px; }}
.home-brand-name {{ font-size: 14px; font-weight: 800; letter-spacing: .02em; color: var(--text); white-space: nowrap; }}
.home-nav {{ display: flex; gap: 4px; margin: 0 auto; }}
.home-nav-item {{
    padding: 7px 14px; border-radius: 999px;
    color: var(--text-secondary); font-size: 13px; font-weight: 600;
    transition: color .15s, background .15s;
}}
.home-nav-item:hover {{ color: var(--text); background: var(--surface-alt); }}
.home-nav-right {{ display: flex; align-items: center; gap: 16px; }}
.home-nav-link {{ font-size: 13px; font-weight: 600; color: var(--text-faint); }}
.home-nav-link:hover {{ color: var(--accent-2); }}

/* Hero */
.home-hero {{
    display: grid; grid-template-columns: 1.05fr .95fr; gap: 48px; align-items: center;
    max-width: 1440px; margin: 0 auto; padding: 72px 44px 88px;
}}
.home-hero-copy {{ animation: home-fade-up .6s ease both; }}
.home-eyebrow {{
    font-size: 11px; font-weight: 700; letter-spacing: .18em;
    text-transform: uppercase; color: var(--accent-2); margin-bottom: 18px;
}}
.home-title {{ font-size: clamp(34px, 5vw, 58px); line-height: 1.04; font-weight: 800; letter-spacing: -.02em; margin: 0 0 22px; }}
.home-title-line {{ display: block; }}
.home-title-accent {{ color: var(--accent-2); }}
.home-lead {{ font-size: 16px; line-height: 1.6; color: var(--text-secondary); max-width: 560px; margin: 0 0 30px; }}
.home-cta {{ display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 30px; }}
.home-btn {{
    display: inline-flex; align-items: center; justify-content: center;
    padding: 13px 26px; border-radius: 999px; font-size: 13px; font-weight: 700;
    letter-spacing: .08em; transition: transform .15s, box-shadow .15s, background .15s;
}}
.home-btn-primary {{ background: var(--accent-2); color: #fff; box-shadow: 0 6px 18px rgba(57,118,210,.28); }}
.home-btn-primary:hover {{ background: #2c63b8; transform: translateY(-1px); box-shadow: 0 10px 24px rgba(57,118,210,.34); }}
.home-btn-ghost {{ border: 1px solid var(--border-strong); background: var(--surface); color: var(--text); }}
.home-btn-ghost:hover {{ border-color: var(--accent-2); color: var(--accent-2); transform: translateY(-1px); }}
.home-hero-flow {{ display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }}
.home-flow-step {{ font-size: 11px; font-weight: 800; letter-spacing: .16em; color: var(--text); }}
.home-flow-arrow {{ color: var(--accent-2); font-weight: 700; }}

/* Hero visual */
.home-hero-visual {{ position: relative; height: 560px; animation: home-fade-in .8s .15s ease both; }}
.hero-grid-bg {{
    position: absolute; inset: 0;
    background-image:
        linear-gradient(var(--border) 1px, transparent 1px),
        linear-gradient(90deg, var(--border) 1px, transparent 1px);
    background-size: 44px 44px; opacity: .5;
    -webkit-mask-image: radial-gradient(circle at 50% 45%, #000 30%, transparent 75%);
    mask-image: radial-gradient(circle at 50% 45%, #000 30%, transparent 75%);
}}
.hero-orbit {{
    position: absolute; left: 50%; top: 50%; width: 380px; height: 380px;
    transform: translate(-50%, -50%);
    border: 1px solid var(--border); border-radius: 50%;
    animation: hero-float 9s ease-in-out infinite;
}}
.hero-orbit::after {{
    content: ""; position: absolute; inset: 36px;
    border: 1px dashed var(--border); border-radius: 50%;
}}
.hero-card {{
    position: absolute; background: var(--surface); border: 1px solid var(--border);
    border-radius: 16px; padding: 16px 18px;
    box-shadow: 0 12px 34px rgba(20,24,23,.08);
    animation: hero-float 7s ease-in-out infinite;
}}
.hero-card-btc {{ left: 5%; top: 12%; width: 205px; z-index: 3; }}
.hero-card-eth {{ right: 3%; top: 7%; width: 205px; z-index: 3; animation-delay: 1.4s; }}
.hero-card-sentiment {{ left: 15%; bottom: 10%; width: 224px; z-index: 4; animation-delay: .6s; }}
.hero-card-spark {{ right: 8%; bottom: 14%; width: 265px; z-index: 3; animation-delay: 1s; }}
.hero-card-vol {{ left: 43%; top: 4%; width: 190px; z-index: 2; animation-delay: .4s; }}
.hero-card-label {{ font-size: 10px; font-weight: 700; letter-spacing: .14em; color: var(--text-faint); text-transform: uppercase; }}
.hero-card-sub {{ font-size: 10px; letter-spacing: .1em; color: var(--text-faint); margin-top: 2px; }}
.hero-card-tag {{ display: flex; align-items: center; gap: 6px; font-size: 11px; font-weight: 700; letter-spacing: .1em; color: var(--text-secondary); margin-top: 8px; }}
.hero-dot {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}
.hero-dot-btc {{ background: #F7931A; }}
.hero-dot-eth {{ background: #627EEA; }}
.hero-card-price {{ font-size: 24px; font-weight: 800; letter-spacing: -.01em; margin-top: 6px; }}
.hero-card-change {{ font-size: 12px; font-weight: 700; margin-top: 2px; }}
.hero-sentiment-value {{ font-size: 44px; font-weight: 800; letter-spacing: -.02em; line-height: 1; margin-top: 6px; }}
.hero-sentiment-label {{ font-size: 11px; font-weight: 800; letter-spacing: .16em; color: var(--accent-2); margin-top: 4px; }}
.hero-gauge {{ height: 6px; border-radius: 999px; background: var(--surface-alt); border: 1px solid var(--border); margin-top: 12px; overflow: hidden; }}
.hero-gauge-fill {{ height: 100%; background: linear-gradient(90deg, var(--accent-2), var(--positive)); border-radius: 999px; }}
.hero-vol-value {{ font-size: 22px; font-weight: 800; margin-top: 6px; }}
.hero-node {{ position: absolute; width: 10px; height: 10px; border-radius: 50%; background: var(--accent-2); box-shadow: 0 0 0 5px rgba(57,118,210,.15); }}
.hero-node-1 {{ left: 33%; top: 33%; }}
.hero-node-2 {{ right: 29%; bottom: 30%; }}
.hero-node-3 {{ left: 50%; top: 58%; width: 6px; height: 6px; }}
#home-hero-spark svg {{ width: 100%; height: 64px; display: block; }}

/* Latest asset news on the homepage */
.home-news {{ max-width: 1440px; margin: 0 auto; padding: 56px 44px 0; }}
.home-news-head {{ margin-bottom: 28px; }}
.home-news-grid {{ grid-auto-flow: column; grid-auto-columns: minmax(250px, 320px); justify-content: start; overflow-x: auto; padding-bottom: 8px; scrollbar-width: thin; }}

/* Feature cards */
.home-features, .home-sections {{ max-width: 1440px; margin: 0 auto; padding: 64px 44px; }}
.home-section-head {{ margin-bottom: 40px; max-width: 640px; }}
.home-section-num {{ font-size: 11px; font-weight: 800; letter-spacing: .2em; color: var(--accent-2); margin-bottom: 12px; }}
.home-section-head h2 {{ font-size: clamp(24px, 3vw, 34px); font-weight: 800; letter-spacing: -.01em; margin: 0 0 8px; }}
.home-section-head p {{ color: var(--text-secondary); font-size: 15px; margin: 0; }}
.home-cards {{ display: grid; grid-template-columns: repeat(12, 1fr); gap: 20px; }}
.span-7 {{ grid-column: span 7; }}
.span-5 {{ grid-column: span 5; }}
.span-8 {{ grid-column: span 8; }}
.span-4 {{ grid-column: span 4; }}
.feature-card {{
    position: relative; display: flex; flex-direction: column;
    background: var(--surface); border: 1px solid var(--border); border-radius: 18px;
    padding: 26px 28px; color: var(--text);
    box-shadow: 0 1px 2px rgba(20,24,23,.03);
    transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
    overflow: hidden;
}}
.feature-card:hover {{ transform: translateY(-4px); box-shadow: 0 18px 40px rgba(20,24,23,.09); border-color: var(--border-strong); }}
.feature-card-head {{ display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }}
.feature-icon {{ width: 40px; height: 40px; border-radius: 12px; display: flex; align-items: center; justify-content: center; background: var(--accent-bg); color: var(--accent); flex: 0 0 auto; }}
.feature-icon svg {{ width: 22px; height: 22px; }}
.icon-svg {{ display: inline-flex; align-items: center; justify-content: center; }}
.icon-svg svg {{ width: 22px; height: 22px; display: block; }}
.home-logo svg {{ width: 30px; height: 30px; display: block; }}
.icon-svg p, #home-hero-spark p, .mini-market-spark p, .mini-forecast p, .mini-backtest p {{ margin: 0; }}
.feature-card-title {{ font-size: 13px; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; color: var(--text); }}
.feature-card-desc {{ font-size: 13.5px; line-height: 1.55; color: var(--text-secondary); margin-bottom: 16px; flex: 1; }}
.feature-card-body {{ margin-bottom: 16px; }}
.feature-card-foot {{ display: flex; align-items: center; gap: 8px; }}
.feature-card-open {{ font-size: 11px; font-weight: 800; letter-spacing: .14em; color: var(--text-faint); text-transform: uppercase; }}
.feature-card-arrow {{ font-size: 16px; color: var(--accent-2); transition: transform .18s ease; }}
.feature-card:hover .feature-card-arrow {{ transform: translateX(5px); }}
.feature-card:hover .feature-card-open {{ color: var(--accent-2); }}

/* Mini previews inside feature cards */
.mini-market-list {{ display: flex; flex-direction: column; }}
.mini-market-row {{ display: flex; align-items: center; gap: 12px; padding: 7px 0; border-bottom: 1px solid var(--border); }}
.mini-market-symbol {{ display: flex; align-items: center; gap: 6px; font-size: 11px; font-weight: 700; letter-spacing: .1em; color: var(--text-secondary); flex: 1; }}
.mini-market-price {{ font-size: 13px; font-weight: 700; }}
.mini-market-change {{ font-size: 12px; font-weight: 700; width: 72px; text-align: right; }}
.mini-market-spark {{ margin-top: 12px; }}
.mini-market-spark svg, .mini-forecast svg, .mini-backtest svg {{ width: 100%; height: 100%; display: block; }}
.mini-forecast, .mini-backtest {{ height: 110px; }}
.mini-chips {{ display: flex; flex-wrap: wrap; gap: 8px; }}
.chip {{ font-size: 11px; font-weight: 700; letter-spacing: .04em; color: var(--text-secondary); border: 1px solid var(--border); background: var(--surface-alt); border-radius: 999px; padding: 5px 11px; }}
.chip-stat {{ color: var(--accent); background: var(--accent-bg); border-color: transparent; }}
.mini-gauge {{ text-align: center; padding: 8px 0; }}
.mini-gauge-score {{ display: inline-flex; align-items: baseline; gap: 4px; }}
.mini-gauge-value {{ font-size: 46px; font-weight: 800; letter-spacing: -.02em; }}
.mini-gauge-max {{ font-size: 14px; font-weight: 700; color: var(--text-faint); }}
.mini-gauge-label {{ font-size: 11px; font-weight: 800; letter-spacing: .16em; color: var(--accent-2); margin-top: 4px; text-transform: uppercase; }}
.mini-gauge-factors {{ display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; margin-top: 14px; }}
.factor {{ font-size: 11px; font-weight: 700; border-radius: 999px; padding: 4px 10px; }}
.factor-pos {{ color: var(--positive); background: var(--positive-bg); }}
.factor-neg {{ color: var(--negative); background: var(--negative-bg); }}
.mini-alerts {{ display: flex; flex-direction: column; gap: 8px; }}
.mini-alert-item {{ display: flex; align-items: center; gap: 10px; font-size: 12px; padding: 9px 12px; border-radius: 10px; background: var(--surface-alt); border: 1px solid var(--border); }}
.mini-alert-sev {{ font-size: 10px; font-weight: 800; letter-spacing: .08em; padding: 2px 7px; border-radius: 999px; }}
.mini-alert-empty {{ font-size: 12px; color: var(--text-faint); padding: 12px; }}
.mini-bars {{ display: flex; flex-direction: column; gap: 8px; padding: 10px 0; }}
.mini-bar {{ height: 9px; border-radius: 999px; background: linear-gradient(90deg, var(--accent-2), #7FA6D9); opacity: .85; }}

/* Section index rows */
.home-section-list {{ display: flex; flex-direction: column; border-top: 1px solid var(--border); }}
.home-section-row {{ display: flex; align-items: flex-start; gap: 28px; padding: 26px 10px; border-bottom: 1px solid var(--border); border-radius: 12px; transition: background .15s; }}
.home-section-row:hover {{ background: var(--surface); }}
.home-section-row-num {{ font-size: 12px; font-weight: 800; letter-spacing: .12em; color: var(--text-faint); width: 40px; flex: 0 0 auto; padding-top: 2px; }}
.home-section-row-main {{ flex: 1; }}
.home-section-row-title {{ font-size: 17px; font-weight: 800; letter-spacing: -.01em; }}
.home-section-row-tagline {{ font-size: 13px; color: var(--accent-2); font-weight: 700; margin-top: 2px; }}
.home-section-row-desc {{ font-size: 13.5px; color: var(--text-secondary); margin-top: 6px; max-width: 640px; line-height: 1.55; }}
.home-section-row-link {{ font-size: 12.5px; font-weight: 700; color: var(--accent-2); white-space: nowrap; padding-top: 4px; }}
.home-section-row:hover .home-section-row-link {{ text-decoration: underline; }}

/* Footer */
.home-footer {{ border-top: 1px solid var(--border); background: var(--surface); margin-top: 24px; }}
.home-footer-grid {{ max-width: 1440px; margin: 0 auto; padding: 48px 44px; display: grid; grid-template-columns: 2fr 1fr 1fr 1fr; gap: 32px; }}
.home-footer-brand {{ display: flex; align-items: center; gap: 10px; }}
.home-footer-name {{ font-size: 14px; font-weight: 800; }}
.home-footer-desc {{ font-size: 13px; color: var(--text-secondary); max-width: 340px; margin: 14px 0 0; line-height: 1.6; }}
.home-footer-head {{ font-size: 11px; font-weight: 800; letter-spacing: .14em; color: var(--text-faint); text-transform: uppercase; margin-bottom: 12px; }}
.home-footer-col {{ display: flex; flex-direction: column; gap: 9px; }}
.home-footer-link {{ font-size: 13px; color: var(--text-secondary); }}
.home-footer-link:hover {{ color: var(--accent-2); }}
.home-footer-legal {{ border-top: 1px solid var(--border); padding: 22px 44px; max-width: 1440px; margin: 0 auto; font-size: 12px; color: var(--text-faint); }}
.home-disclaimer {{ margin: 10px 0 0; max-width: 760px; line-height: 1.55; color: var(--text-faint); }}

/* Reveal / scroll behaviour */
.reveal {{ opacity: 0; transform: translateY(22px); transition: opacity .6s ease, transform .6s ease; }}
.reveal.revealed {{ opacity: 1; transform: none; }}
.home-section-row, section[id] {{ scroll-margin-top: 84px; }}

@keyframes home-fade-up {{ from {{ opacity: 0; transform: translateY(16px); }} to {{ opacity: 1; transform: none; }} }}
@keyframes home-fade-in {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
@keyframes hero-float {{ 0%,100% {{ transform: translateY(0); }} 50% {{ transform: translateY(-8px); }} }}

@media (max-width: 1080px) {{
    .home-hero {{ grid-template-columns: 1fr; padding: 56px 28px 64px; }}
    .home-hero-visual {{ height: 520px; }}
    .home-nav {{ display: none; }}
    .home-cards {{ grid-template-columns: 1fr 1fr; }}
    .span-7, .span-5, .span-8, .span-4 {{ grid-column: span 1; }}
    .home-news-grid {{ grid-auto-flow: row; grid-auto-columns: auto; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }}
    .home-footer-grid {{ grid-template-columns: 1fr 1fr; }}
}}
@media (max-width: 640px) {{
    .home-header {{ padding: 12px 18px; }}
    .home-nav-right {{ display: none; }}
    .home-hero-visual {{ height: 470px; }}
    .hero-card-btc {{ left: 2%; top: 6%; }}
    .hero-card-eth {{ right: 2%; top: 2%; }}
    .home-cards {{ grid-template-columns: 1fr; }}
    .home-footer-grid {{ grid-template-columns: 1fr; padding: 32px 24px; }}
    .home-features, .home-sections {{ padding: 44px 20px; }}
    .home-news {{ padding: 44px 20px 0; }}
    .home-hero {{ padding: 44px 20px 56px; }}
}}
"""


def apply_theme(fig: go.Figure, height: int | None = None,
                tokens: dict | None = None, **layout_kwargs) -> go.Figure:
    """Apply the shared chart language to a figure."""
    t = tokens or TOKENS
    layout: dict = dict(
        font=dict(family=FONT_STACK, color=t["text"], size=12),
        paper_bgcolor=t["surface"],
        plot_bgcolor=t["surface"],
        margin=dict(l=10, r=10, t=30, b=10),
        height=height,
        hoverlabel=dict(bgcolor=t["surface"], bordercolor=t["border"],
                        font=dict(color=t["text"], size=12)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(gridcolor=t["grid"], zeroline=False, linecolor=t["border"]),
        yaxis=dict(gridcolor=t["grid"], zeroline=False, linecolor=t["border"]),
        colorway=t["chart_palette"],
    )
    if "title" not in layout_kwargs:
        layout["title"] = dict(text="", font=dict(size=12))
    layout.update(layout_kwargs)
    fig.update_layout(**layout)
    return fig


def empty_figure(height: int = 300) -> go.Figure:
    return apply_theme(go.Figure(), height=height)
