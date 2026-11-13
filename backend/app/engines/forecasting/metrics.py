from typing import Dict
import numpy as np


def calculate_metrics(
    y_true: np.ndarray, y_pred: np.ndarray
) -> Dict[str, float | int | None]:
    """
    Computes standard retail demand forecasting evaluation metrics:
    - MAE: Mean Absolute Error
    - RMSE: Root Mean Squared Error
    - WAPE: Weighted Absolute Percentage Error; undefined (None) when total actual
      demand is zero because the denominator is zero.
    - Forecast Bias: Mean error (positive = overforecasting, negative = underforecasting)
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    if len(y_true) == 0:
        return {"mae": 0.0, "rmse": 0.0, "wape": None, "bias": 0.0, "sample_size": 0}

    errors = y_pred - y_true
    abs_errors = np.abs(errors)

    mae_val = float(np.mean(abs_errors))
    rmse_val = float(np.sqrt(np.mean(errors ** 2)))

    sum_true = float(np.sum(y_true))
    wape_val = float(np.sum(abs_errors) / sum_true) if sum_true > 1e-6 else None
    bias_val = float(np.mean(errors))

    return {
        "mae": round(mae_val, 4),
        "rmse": round(rmse_val, 4),
        "wape": round(wape_val, 4) if wape_val is not None else None,
        "bias": round(bias_val, 4),
        "sample_size": len(y_true),
    }

