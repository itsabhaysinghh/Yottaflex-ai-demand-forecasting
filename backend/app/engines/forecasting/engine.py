from datetime import date, timedelta
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

from app.engines.forecasting.base import BaseForecaster
from app.engines.forecasting.moving_average import MovingAverageForecaster
from app.engines.forecasting.seasonal_naive import SeasonalNaiveForecaster
from app.engines.forecasting.exponential_smoothing import ExponentialSmoothingForecaster
from app.engines.forecasting.croston import CrostonForecaster
from app.engines.forecasting.metrics import calculate_metrics
from app.engines.forecasting.censoring import adjust_stockout_censoring

FORECASTER_REGISTRY = {
    "moving_average": MovingAverageForecaster,
    "seasonal_naive": SeasonalNaiveForecaster,
    "exponential_smoothing": ExponentialSmoothingForecaster,
    "croston": CrostonForecaster,
}


class ForecastingEngine:
    """
    Orchestrates demand forecasting pipelines:
    - Stockout-censored demand adjustment
    - Strict temporal train/test split (guaranteeing zero future data leakage)
    - Multi-model statistical baseline fitting
    - Out-of-sample backtest metrics calculation (MAE, RMSE, WAPE, Bias)
    - Future horizon projection generation
    """

    @classmethod
    def get_forecaster(cls, model_name: str, **kwargs) -> BaseForecaster:
        factory = FORECASTER_REGISTRY.get(model_name.lower())
        if not factory:
            raise ValueError(f"Unknown forecasting model '{model_name}'. Available: {list(FORECASTER_REGISTRY.keys())}")
        return factory(**kwargs)

    @classmethod
    def run_temporal_evaluation(
        cls,
        history_df: pd.DataFrame,
        model_name: str = "moving_average",
        test_horizon_days: int = 14,
        adjust_censoring: bool = True,
    ) -> Dict[str, Any]:
        """
        Executes an out-of-sample temporal backtest without future-data leakage.
        Splits into:
          Train: [T_0, T_cutoff]
          Test:  (T_cutoff, T_cutoff + test_horizon_days]
        """
        if len(history_df) < test_horizon_days + 7:
            raise ValueError("Insufficient historical observations for temporal evaluation.")

        # Ensure sorted by date
        df = history_df.sort_values("sale_date").reset_index(drop=True)

        cutoff_idx = len(df) - test_horizon_days
        train_df = df.iloc[:cutoff_idx].copy()
        test_df = df.iloc[cutoff_idx:].copy()

        # Strict temporal leakage assertion:
        train_max_date = train_df["sale_date"].max()
        test_min_date = test_df["sale_date"].min()
        assert train_max_date < test_min_date, f"Temporal leakage detected! {train_max_date} >= {test_min_date}"

        # Adjust censoring on training data only (to avoid lookahead bias)
        if adjust_censoring and "stockout_flag" in train_df.columns:
            y_train = adjust_stockout_censoring(train_df).to_numpy()
        else:
            y_train = train_df["units_sold"].astype(float).to_numpy()

        y_test = test_df["units_sold"].astype(float).to_numpy()

        forecaster = cls.get_forecaster(model_name)
        forecaster.fit(y_train)
        point_pred, lower_pred, upper_pred = forecaster.predict(horizon_days=test_horizon_days)

        metrics = calculate_metrics(y_true=y_test, y_pred=point_pred)

        return {
            "model_name": model_name,
            "train_max_date": train_max_date,
            "test_min_date": test_min_date,
            "test_horizon_days": test_horizon_days,
            "metrics": metrics,
            "y_test": y_test.tolist(),
            "y_pred": point_pred.tolist(),
            "model_params": forecaster.params,
        }

    @classmethod
    def generate_future_forecast(
        cls,
        history_df: pd.DataFrame,
        model_name: str = "moving_average",
        horizon_days: int = 14,
        cutoff_date: Optional[date] = None,
        adjust_censoring: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Fits on all historical data up to cutoff_date and projects demand over horizon_days into future.
        """
        df = history_df.sort_values("sale_date").reset_index(drop=True)
        if cutoff_date is not None:
            df = df[df["sale_date"] <= cutoff_date]

        if df.empty:
            raise ValueError("No sales history available to generate forecast.")

        effective_cutoff = df["sale_date"].max()

        if adjust_censoring and "stockout_flag" in df.columns:
            y_train = adjust_stockout_censoring(df).to_numpy()
        else:
            y_train = df["units_sold"].astype(float).to_numpy()

        forecaster = cls.get_forecaster(model_name)
        forecaster.fit(y_train)
        point_pred, lower_pred, upper_pred = forecaster.predict(horizon_days=horizon_days)

        forecasts = []
        for step in range(1, horizon_days + 1):
            target_dt = effective_cutoff + timedelta(days=step)
            idx = step - 1
            forecasts.append({
                "model_name": model_name,
                "forecast_date": effective_cutoff,
                "target_date": target_dt,
                "horizon_days": step,
                "predicted_units": round(float(point_pred[idx]), 2),
                "confidence_lower": round(float(lower_pred[idx]), 2),
                "confidence_upper": round(float(upper_pred[idx]), 2),
                "model_params": forecaster.params,
            })

        return forecasts

