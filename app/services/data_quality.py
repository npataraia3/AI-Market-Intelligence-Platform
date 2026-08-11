from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd


def _freshness_age(timestamp_ms: int) -> dict:
    now = datetime.now(timezone.utc)
    observed = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
    age_seconds = max(0.0, (now - observed).total_seconds())
    return {
        "last_observed_utc": observed.isoformat(),
        "age_minutes": round(age_seconds / 60, 1),
        "fresh": age_seconds < 12 * 3600,
    }


def check_data_quality(history: dict, fear_greed: list[dict] | None = None) -> dict:
    """Schema, completeness, duplication, outlier and freshness checks on the
    raw provider payloads (independent of the modelling pipeline)."""
    checks: list[dict] = []
    issues: list[str] = []

    # --- Schema ---
    required = ("prices", "total_volumes")
    missing_keys = [key for key in required if key not in history]
    checks.append({
        "check": "schema",
        "status": "OK" if not missing_keys else "FAIL",
        "detail": "required keys present" if not missing_keys else f"Missing keys: {', '.join(missing_keys)}",
    })
    if missing_keys:
        issues.append("Provider payload missing required keys.")
        return {"healthy": False, "checks": checks, "issues": issues}

    prices = history["prices"]
    volumes = history.get("total_volumes") or []
    price_df = pd.DataFrame(prices, columns=["ts", "price"])
    volume_df = pd.DataFrame(volumes, columns=["ts", "volume"])

    # --- Completeness / missing values ---
    if price_df.empty:
        checks.append({"check": "missing_values", "status": "FAIL", "detail": "No price points returned."})
        issues.append("Empty price history.")
    else:
        expected = len(price_df)
        merged = price_df.merge(volume_df, on="ts", how="left")
        missing_price = float(price_df["price"].isna().mean() * 100)
        missing_volume = float(merged["volume"].isna().mean() * 100)
        checks.append({"check": "missing_values", "status": "OK" if missing_volume < 10 else "WARN",
                       "detail": f"price {missing_price:.1f}%, volume {missing_volume:.1f}%"})
        if missing_volume >= 10:
            issues.append("More than 10% of volume values are missing.")

    # --- Duplicate timestamps ---
    duplicate_count = int(price_df.duplicated("ts").sum())
    checks.append({"check": "duplicates", "status": "OK" if duplicate_count == 0 else "WARN",
                   "detail": f"{duplicate_count} duplicate timestamps"})
    if duplicate_count:
        issues.append("Duplicate timestamps detected.")

    # --- Outliers / unexpected price jumps ---
    if len(price_df) > 5:
        series = price_df["price"].astype(float)
        mean, std = series.mean(), series.std()
        if std > 0:
            z_scores = np.abs((series - mean) / std)
            outliers = int((z_scores > 5).sum())
            checks.append({"check": "outliers", "status": "OK" if outliers == 0 else "WARN",
                           "detail": f"{outliers} price points beyond 5-sigma"})
            jumps = price_df["price"].pct_change()
            huge = jumps.abs().dropna()
            threshold = 6 * std / max(mean, 1e-9)
            jump_count = int((huge > max(threshold, 0.5)).sum())
            checks.append({"check": "price_jumps", "status": "OK" if jump_count == 0 else "WARN",
                           "detail": f"{jump_count} day(s) with return beyond {max(threshold, 0.5) * 100:.0f}%"})
            if jump_count:
                issues.append("Unusually large day-over-day price jumps detected.")
        else:
            checks.append({"check": "outliers", "status": "OK", "detail": "constant series"})

    # --- Freshness ---
    if price_df.empty:
        checks.append({"check": "freshness", "status": "FAIL", "detail": "no data"})
    else:
        freshness = _freshness_age(int(price_df["ts"].iloc[-1]))
        checks.append({"check": "freshness", "status": "OK" if freshness["fresh"] else "WARN",
                       "detail": f"last point {freshness['age_minutes']:.0f} min ago ({freshness['last_observed_utc']})"})
        if not freshness["fresh"]:
            issues.append("Data is older than 12 hours — provider may be stale.")

    # --- Fear & Greed completeness ---
    fear_records = fear_greed or []
    if fear_records:
        values = pd.to_numeric(pd.Series([record.get("value") for record in fear_records]), errors="coerce")
        missing = float(values.isna().mean() * 100)
        checks.append({"check": "fear_greed", "status": "OK" if missing < 20 else "WARN",
                       "detail": f"{missing:.1f}% missing values"})

    healthy = all(check["status"] == "OK" for check in checks)
    return {"healthy": healthy, "checks": checks, "issues": issues}
