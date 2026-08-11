from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _linear_contributions(model, row: pd.Series, columns: list[str]) -> list[dict]:
    """Exact per-feature contribution for linear models: coef * feature."""
    coefficients = np.asarray(model.coef_)
    values = row[columns].to_numpy()
    contributions = coefficients * values
    base = float(model.intercept_)
    return _format_contributions(columns, contributions, base)


def _shap_contributions(model, X: pd.DataFrame, index: int = -1) -> list[dict]:
    """SHAP local explanation via TreeExplainer (exact for tree ensembles)."""
    import shap

    explainer = shap.TreeExplainer(model)
    values = explainer.shap_values(X)
    row_values = np.asarray(values[index] if values.ndim > 1 else values)
    base = float(explainer.expected_value if not isinstance(explainer.expected_value, np.ndarray) else explainer.expected_value[0])
    return _format_contributions(list(X.columns), row_values, base)


def _format_contributions(columns: list[str], values: np.ndarray, base: float) -> list[dict]:
    return [
        {"feature": column, "contribution": round(float(value), 5)}
        for column, value in zip(columns, values)
    ] + [{"feature": "base", "contribution": round(base, 5)}]


def explain_prediction(model, X: pd.DataFrame, index: int = -1, model_kind: str = "xgboost") -> dict:
    """Local explanation for a single prediction.

    Uses exact SHAP when available (TreeExplainer for XGBoost, coefficient
    contributions for linear models) and degrades gracefully to feature-gain
    importance if the SHAP package is unavailable.
    """
    try:
        import shap  # noqa: F401

        if model_kind == "linear":
            contributions = _linear_contributions(model, X.iloc[index], list(X.columns))
        else:
            contributions = _shap_contributions(model, X, index)
        method = "SHAP" if model_kind != "linear" else "Linear coefficient contributions (exact SHAP for linear models)"
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning("SHAP unavailable (%s); falling back to gain importance.", exc)
        importance = sorted(zip(X.columns, model.feature_importances_), key=lambda pair: pair[1], reverse=True)
        contributions = [{"feature": feature, "contribution": round(float(value), 5)} for feature, value in importance]
        method = "Gain importance (SHAP unavailable)"
    return {"method": method, "contributions": contributions}


def global_importance(model, X: pd.DataFrame, model_kind: str = "xgboost") -> dict:
    """Global feature importance from mean |SHAP value| across the sample."""
    try:
        import shap  # noqa: F401

        if model_kind == "linear":
            importance = sorted(zip(X.columns, np.abs(model.coef_)), key=lambda pair: pair[1], reverse=True)
            values = [float(value) for _, value in importance]
            method = "|coef| (linear)"
        else:
            explainer = shap.TreeExplainer(model)
            values = np.asarray(explainer.shap_values(X))
            mean_abs = np.abs(values).mean(axis=0)
            importance = sorted(zip(X.columns, mean_abs), key=lambda pair: pair[1], reverse=True)
            values = [float(value) for _, value in importance]
            method = "mean |SHAP|"
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning("SHAP unavailable (%s); falling back to gain importance.", exc)
        importance = sorted(zip(X.columns, model.feature_importances_), key=lambda pair: pair[1], reverse=True)
        values = [float(value) for _, value in importance]
        method = "Gain importance (SHAP unavailable)"
    return {
        "method": method,
        "features": [{"feature": feature, "importance": round(value, 5)} for feature, value in zip(X.columns, values)],
    }
