from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


ANNUALIZATION = 365


def _rolling_volatility(prices: pd.Series, window: int = 30) -> pd.Series:
    returns = prices.pct_change().dropna()
    return returns.rolling(window, min_periods=5).std() * np.sqrt(ANNUALIZATION)


def rule_based_regime(frame: pd.DataFrame) -> dict:
    """Classify the current market using transparent, deterministic rules.

    Trend comes from the price vs its 30-day moving average combined with the
    30-day return; volatility is measured against the historical distribution
    of rolling 30-day annualized volatility.
    """
    prices = frame["price_usd"]
    if len(prices) < 5:
        return {"regime": "INSUFFICIENT DATA", "trend": "UNKNOWN", "volatility": "UNKNOWN", "evidence": {}}

    sma_30 = frame["sma_30"].iloc[-1]
    current_price = float(prices.iloc[-1])
    return_30 = float(prices.iloc[-1] / prices.iloc[-8 - 1] - 1) if len(prices) > 9 else float(prices.iloc[-1] / prices.iloc[0] - 1)

    if current_price > sma_30 and return_30 > 0:
        trend = "BULL"
    elif current_price < sma_30 and return_30 < 0:
        trend = "BEAR"
    else:
        trend = "SIDEWAYS"

    rolling_vol = _rolling_volatility(prices)
    recent_vol = float(rolling_vol.iloc[-1])
    historical = rolling_vol.dropna()
    if historical.empty or not np.isfinite(recent_vol):
        volatility = "NORMAL"
        percentile = None
    else:
        percentile = float((historical <= recent_vol).mean() * 100)
        if percentile >= 75:
            volatility = "HIGH"
        elif percentile <= 25:
            volatility = "LOW"
        else:
            volatility = "NORMAL"

    regime = trend if volatility == "NORMAL" else f"{trend} · {volatility} VOLATILITY"
    return {
        "regime": regime,
        "trend": trend,
        "volatility": volatility,
        "evidence": {
            "price": round(current_price, 4),
            "sma_30": round(float(sma_30), 4),
            "price_above_sma_30": bool(current_price > sma_30),
            "return_30d_percent": round(return_30 * 100, 3),
            "volatility_30d_percent": round(recent_vol * 100, 3),
            "volatility_percentile": round(percentile, 1) if percentile is not None else None,
        },
    }


def _regime_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Rolling window features used by the unsupervised regime discovery."""
    prices = frame["price_usd"]
    returns = prices.pct_change()
    volume = frame.get("volume_usd", pd.Series(0.0, index=prices.index))
    rsi = frame.get("rsi_14", pd.Series(50.0, index=prices.index))
    features = pd.DataFrame(index=prices.index)
    features["volatility"] = returns.rolling(14, min_periods=5).std() * np.sqrt(ANNUALIZATION)
    features["return_1"] = returns
    features["return_7"] = prices.pct_change(7)
    features["volume_z"] = (volume - volume.rolling(30, min_periods=5).mean()) / volume.rolling(30, min_periods=5).std().replace(0, np.nan)
    features["rsi"] = rsi
    features["sma_distance"] = prices / frame.get("sma_30", prices.rolling(30).mean()) - 1
    features["bollinger_width"] = (frame.get("bollinger_upper", prices) - frame.get("bollinger_lower", prices)) / prices
    return features


def cluster_regimes(frame: pd.DataFrame, n_clusters: int = 3) -> dict:
    """Discover recurring market states with KMeans on standardized features.

    Clusters are labelled post-hoc by their centroid characteristics so the
    unsupervised output maps back to the interpretable BULL / BEAR / SIDEWAYS
    vocabulary used by the rule-based detector.
    """
    features = _regime_features(frame).dropna()
    if len(features) < n_clusters * 20:
        return {"available": False, "clusters": []}

    scaled = StandardScaler().fit_transform(features)
    kmeans = KMeans(n_clusters=n_clusters, n_init=10, random_state=42).fit(scaled)
    features["cluster"] = kmeans.labels_

    cluster_stats = []
    for cluster_id in range(n_clusters):
        members = features[features["cluster"] == cluster_id]
        if members.empty:
            continue
        mean_return = float(members["return_1"].mean() * ANNUALIZATION * 100)
        mean_vol = float(members["volatility"].mean() * 100)
        if mean_return > 0.5:
            trend = "BULL"
        elif mean_return < -0.5:
            trend = "BEAR"
        else:
            trend = "SIDEWAYS"
        volatility = "HIGH" if mean_vol > float(features["volatility"].mean() * 100) else "LOW" if mean_vol < float(features["volatility"].median() * 100) else "NORMAL"
        cluster_stats.append({
            "cluster": int(cluster_id), "label": trend, "volatility": volatility,
            "mean_annual_return_percent": round(mean_return, 2),
            "mean_annual_volatility_percent": round(mean_vol, 2),
            "size": int(len(members)),
        })

    current_cluster = int(features["cluster"].iloc[-1])
    current_stats = next((row for row in cluster_stats if row["cluster"] == current_cluster), None)
    return {
        "available": True,
        "method": "KMeans (k={0}, standardized rolling features, post-hoc labels)".format(n_clusters),
        "current_cluster": current_cluster,
        "current_label": current_stats["label"] if current_stats else "UNKNOWN",
        "current_regime": (current_stats["label"] + (f" · {current_stats['volatility']} VOLATILITY" if current_stats and current_stats["volatility"] != "NORMAL" else "")) if current_stats else "UNKNOWN",
        "clusters": cluster_stats,
    }


def detect_regime(frame: pd.DataFrame) -> dict:
    """Full regime analysis: rule-based detector plus unsupervised discovery."""
    rules = rule_based_regime(frame)
    ml = cluster_regimes(frame)
    return {
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "rule_based": rules,
        "unsupervised": ml,
        "consensus": (rules["trend"] if ml.get("current_label") in {None, rules["trend"]} else f"{rules['trend']} / {ml['current_label']}"),
    }
