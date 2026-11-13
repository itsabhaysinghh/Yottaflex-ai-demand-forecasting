from datetime import date, timedelta
import numpy as np
import pandas as pd
import pytest

from app.engines.forecasting import (
    ForecastingEngine,
    MovingAverageForecaster,
    SeasonalNaiveForecaster,
    ExponentialSmoothingForecaster,
    CrostonForecaster,
    calculate_metrics,
    adjust_stockout_censoring,
)


@pytest.fixture
def synthetic_sales_series():
    dates = [date(2026, 1, 1) + timedelta(days=i) for i in range(45)]
    # 7-day pattern with weekend spikes
    base = [8, 9, 10, 11, 15, 18, 14]
    sales = [base[i % 7] for i in range(45)]
    stockouts = [False] * 45
    # Inject 2 stockout days where sales dropped to zero
    stockouts[10] = True
    sales[10] = 0
    stockouts[20] = True
    sales[20] = 0

    return pd.DataFrame({
        "sale_date": dates,
        "units_sold": sales,
        "stockout_flag": stockouts,
        "day_of_week": [d.weekday() for d in dates],
    })


def test_temporal_leakage_prevention(synthetic_sales_series):
    """
    Asserts that the temporal train/test split strictly prevents lookahead bias:
    max(train_date) must be strictly less than min(test_date).
    """
    res = ForecastingEngine.run_temporal_evaluation(
        history_df=synthetic_sales_series,
        model_name="seasonal_naive",
        test_horizon_days=7,
    )
    assert res["train_max_date"] < res["test_min_date"]
    assert len(res["y_test"]) == 7
    assert len(res["y_pred"]) == 7


def test_censored_demand_adjustment(synthetic_sales_series):
    """
    Verifies that stockout days (sales=0 due to stockout) are correctly unconstrained.
    """
    adjusted = adjust_stockout_censoring(synthetic_sales_series)
    # Day 10 and 20 were artificial stockouts with sales=0
    assert adjusted.iloc[10] > 0, "Stockout day was not imputed!"
    assert adjusted.iloc[20] > 0, "Stockout day was not imputed!"


def test_forecast_evaluation_metrics():
    """
    Verifies MAE, RMSE, WAPE, and Bias formulas.
    """
    y_true = np.array([10.0, 20.0, 30.0, 40.0])
    y_pred = np.array([12.0, 18.0, 33.0, 41.0])
    # Errors: [+2, -2, +3, +1] -> Abs errors: [2, 2, 3, 1]
    # Sum abs errors = 8, mean abs error = 2.0
    # Sum squared errors = 4 + 4 + 9 + 1 = 18 -> mean = 4.5 -> RMSE = sqrt(4.5) ~ 2.1213
    # Sum true = 100 -> WAPE = 8 / 100 = 0.08
    # Mean error (Bias) = (2 - 2 + 3 + 1) / 4 = 1.0
    metrics = calculate_metrics(y_true, y_pred)
    assert metrics["mae"] == 2.0
    assert metrics["rmse"] == round(float(np.sqrt(4.5)), 4)
    assert metrics["wape"] == 0.08
    assert metrics["bias"] == 1.0


def test_croston_intermittent_forecaster():
    """
    Verifies that Croston's method handles intermittent / zero-heavy series.
    """
    # Lumpy demand: non-zero once every 3 periods
    y = np.array([0, 0, 12, 0, 0, 15, 0, 0, 10, 0, 0, 14])
    forecaster = CrostonForecaster(alpha=0.15, use_sba=True)
    forecaster.fit(y)
    point, lower, upper = forecaster.predict(horizon_days=5)
    assert len(point) == 5
    assert point[0] > 0
    # Rate should be roughly demand_size / 3
    assert 2.0 <= point[0] <= 6.0



@pytest.mark.parametrize(
    ("actual", "predicted", "expected"),
    [
        ([0.0], [0.0], None),
        ([0.0], [5.0], None),
        ([10.0], [0.0], 1.0),
        ([10.0, 20.0, 30.0, 40.0], [12.0, 18.0, 33.0, 41.0], 0.08),
        ([0.0, 10.0, 0.0], [5.0, 8.0, 2.0], 0.9),
    ],
)
def test_wape_handles_zero_and_mixed_actual_demand(actual, predicted, expected):
    metrics = calculate_metrics(np.array(actual), np.array(predicted))
    assert metrics["wape"] == expected


def test_wape_is_undefined_for_empty_input():
    metrics = calculate_metrics(np.array([]), np.array([]))
    assert metrics["wape"] is None


@pytest.mark.parametrize("series_length", [14, 17, 5])
def test_exponential_smoothing_forecasts_from_next_seasonal_phase(series_length):
    y = np.arange(1, series_length + 1, dtype=float)
    forecaster = ExponentialSmoothingForecaster(season_length=7).fit(y)

    point, _, _ = forecaster.predict(horizon_days=2)

    expected = max(0.0, forecaster.level + forecaster.seasonals[series_length % 7])
    next_expected = max(0.0, forecaster.level + forecaster.seasonals[(series_length + 1) % 7])
    assert point[0] == pytest.approx(expected)
    assert point[1] == pytest.approx(next_expected)
    if series_length >= 14 and series_length % 7:
        assert point[0] != pytest.approx(forecaster.level + forecaster.seasonals[0])
