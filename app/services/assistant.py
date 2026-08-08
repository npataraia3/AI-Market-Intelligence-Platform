from __future__ import annotations


def market_summary(snapshot: dict) -> str:
    """Explain a snapshot using transparent, deterministic rules (no paid LLM)."""
    change = float(snapshot.get("change_24h_percent") or 0)
    price = float(snapshot["price_usd"])
    if change >= 5:
        state = "strong upward movement"
        note = "Volatility is elevated; avoid treating a one-day move as a guarantee."
    elif change >= 1:
        state = "moderate upward movement"
        note = "The short-term direction is positive, but should be checked against a longer history."
    elif change <= -5:
        state = "strong downward movement"
        note = "Volatility is elevated; inspect volume and broader market conditions."
    elif change <= -1:
        state = "moderate downward movement"
        note = "The short-term direction is negative, but this is not an investment recommendation."
    else:
        state = "largely stable movement"
        note = "The 24-hour change is small relative to the alert threshold."
    return (
        f"{snapshot['name']} is trading at ${price:,.2f}, with {change:+.2f}% over 24 hours. "
        f"This indicates {state}. {note}"
    )
