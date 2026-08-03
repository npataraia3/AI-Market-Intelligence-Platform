from __future__ import annotations

import logging

from app.core.config import settings
from app.data.database import save_alert

logger = logging.getLogger(__name__)


def create_alerts(rows: list[dict]) -> list[dict]:
    alerts: list[dict] = []
    for row in rows:
        change = float(row.get("price_change_percentage_24h") or 0)
        if abs(change) < settings.alert_threshold_percent:
            continue
        severity = "high" if abs(change) >= settings.alert_threshold_percent * 2 else "medium"
        direction = "rose" if change > 0 else "fell"
        message = f"{row['name']} {direction} {abs(change):.2f}% in the past 24 hours."
        alert = {"coin_id": row["id"], "severity": severity, "message": message, "change_24h_percent": change}
        save_alert(row["id"], severity, message, change)
        logger.warning(message)
        alerts.append(alert)
    return alerts
