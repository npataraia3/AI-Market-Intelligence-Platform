"""Reusable UI builders shared across pages.

Every element is rendered from the theme tokens in ``theme.py``; page
modules combine these primitives instead of hand-writing inline styles.
"""

from __future__ import annotations

from dash import dash_table, html

from dashboard.theme import TOKENS


def _fixed(precision: int):
    return dash_table.Format.Format(precision=precision, scheme=dash_table.Format.Scheme.fixed)


def price_format(value: float | None) -> str:
    if value is None:
        return "—"
    if value >= 1:
        return f"${value:,.2f}"
    return f"${value:,.4f}"


def fmt_pct(value: float | None, signed: bool = True) -> str:
    if value is None:
        return "—"
    return f"{value:+.2f}%" if signed else f"{value:.2f}%"


def help_badge(title: str) -> html.Span:
    return html.Span("?", className="help-badge", title=title)


def page_heading(title: str, subtitle: str = "", help: str = "") -> html.Div:
    children: list = [html.H1(title)]
    if help:
        children[0].children = [title, help_badge(help)]
    if subtitle:
        children.append(html.P(subtitle))
    return html.Div(children, className="page-heading")


def section_title(label: str, help: str = "") -> html.Div:
    children = [label]
    if help:
        children.append(help_badge(help))
    return html.Div(children, className="card-title")


def card(children, title: str = "", help: str = "", style: dict | None = None,
         className: str = "card") -> html.Div:
    kids = list(children) if isinstance(children, list) else [children]
    if title:
        kids.insert(0, section_title(title, help))
    return html.Div(kids, className=className, style=style)


def stat_card(label: str, value: str, sub: str = "", tone: str | None = None) -> html.Div:
    tone_colors = {
        "positive": TOKENS["positive"],
        "negative": TOKENS["negative"],
        "warning": TOKENS["warning"],
        "accent": TOKENS["accent"],
        "info": TOKENS["accent_2"],
    }
    border_left = tone_colors.get(tone, TOKENS["border_strong"])
    return html.Div(
        [
            html.Div(label, className="stat-label"),
            html.Div(value, className="stat-value", style={"color": tone_colors.get(tone, TOKENS["text"])}),
            html.Div(sub, className="stat-sub"),
        ],
        className="stat-card",
        style={"border-left": f"3px solid {border_left}"},
    )


def pill(text: str, tone: str = "neutral") -> html.Span:
    return html.Span(text, className=f"pill {tone}")


def alert_item(alert: dict) -> html.Div:
    severity = str(alert.get("severity") or "medium").lower()
    tone = {"high": "negative", "medium": "warning", "low": "info"}.get(severity, "neutral")
    coin = (alert.get("coin_id") or "").replace("-", " ").title()
    message = alert.get("message") or ""
    return html.Div(
        [
            html.Div(
                [
                    pill(severity.upper(), tone),
                    html.Span(f" {coin}", style={"font-weight": 700, "margin-left": "6px"}),
                ]
            ),
            html.Div(message, style={"margin-top": "3px", "color": TOKENS["text_secondary"], "font-size": "12px"}),
            html.Div(_age_label(alert.get("created_at")),
                     style={"color": TOKENS["text_faint"], "font-size": "11px", "margin-top": "2px"}),
        ],
        className=f"alert-item {severity}",
    )


def _age_label(created_at) -> str:
    if not created_at:
        return ""
    from datetime import datetime, timezone
    try:
        created = datetime.fromisoformat(created_at)
    except ValueError:
        return ""
    minutes = int((datetime.now(timezone.utc) - created).total_seconds() / 60)
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes} min ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    return f"{hours // 24}d ago"


def insight_card(label: str, children) -> html.Div:
    return html.Div([html.Div(label, className="insight-label")] + list(children), className="insight-card")


def base_table(columns: list, data: list, conditional: list | None = None,
               extra_style: dict | None = None) -> dash_table.DataTable:
    return dash_table.DataTable(
        columns=columns,
        data=data,
        sort_action="native",
        style_cell={
            "textAlign": "left",
            "fontFamily": "inherit",
            "fontSize": "12px",
            "padding": "7px 10px",
            "backgroundColor": TOKENS["surface"],
            "color": TOKENS["text"],
            "border": f"1px solid {TOKENS['border']}",
        },
        style_header={
            "fontWeight": 700,
            "backgroundColor": TOKENS["surface_alt"],
            "color": TOKENS["text_secondary"],
            "border": f"1px solid {TOKENS['border']}",
            "fontSize": "11px",
            "textTransform": "uppercase",
            "letterSpacing": ".04em",
        },
        style_data_conditional=conditional or [],
        style_table={"overflowX": "auto", "borderRadius": "8px"},
        **(extra_style or {}),
    )
