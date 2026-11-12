import numpy as np
import pandas as pd


def adjust_stockout_censoring(
    df: pd.DataFrame,
    sales_col: str = "units_sold",
    stockout_col: str = "stockout_flag",
    dow_col: str = "day_of_week",
) -> pd.Series:
    """
    Adjusts demand series to compensate for stockout-censored observations.
    When a stockout occurs, observed sales drops to zero or near-zero because of lack
    of stock, not lack of demand.
    
    This function imputes unconstrained demand for stockout days using the median
    sales of non-stockout days for the same day-of-week.
    """
    series = df[sales_col].astype(float).copy()
    stockout_mask = df[stockout_col].astype(bool)

    if not stockout_mask.any():
        return series

    # Calculate day-of-week unconstrained baselines (non-stockout days)
    unconstrained = df[~stockout_mask]
    if unconstrained.empty:
        # Fallback if all days were stockouts
        return series

    dow_medians = unconstrained.groupby(dow_col)[sales_col].median()
    overall_median = unconstrained[sales_col].median()

    for idx in series[stockout_mask].index:
        dow = df.loc[idx, dow_col] if dow_col in df.columns else None
        imputed = dow_medians.get(dow, overall_median)
        # Demand must be at least the observed sales that day
        series.loc[idx] = max(series.loc[idx], float(imputed))

    return series

