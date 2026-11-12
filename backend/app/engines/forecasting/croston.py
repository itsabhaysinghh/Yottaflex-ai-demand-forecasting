from typing import Tuple
import numpy as np
from app.engines.forecasting.base import BaseForecaster


class CrostonForecaster(BaseForecaster):
    """
    Croston's Method for intermittent / slow-moving demand series.
    Separates demand size estimation from inter-arrival interval estimation.
    Includes Syntetos-Boylan Approximation (SBA) debiasing factor.
    """

    def __init__(self, alpha: float = 0.15, use_sba: bool = True):
        super().__init__(name="croston")
        self.alpha = alpha
        self.use_sba = use_sba
        self.params = {"alpha": alpha, "use_sba": use_sba}
        self.demand_rate = 0.0
        self.std_demand = 0.5

    def fit(self, y: np.ndarray, **kwargs) -> "CrostonForecaster":
        y = np.asarray(y, dtype=float)
        non_zero_indices = np.where(y > 0)[0]

        if len(non_zero_indices) == 0:
            self.demand_rate = 0.0
            self.std_demand = 0.1
            self.fitted = True
            return self

        # Initialize demand size and intervals using empirical means of non-zero occurrences
        if len(non_zero_indices) > 1:
            intervals = np.diff(non_zero_indices).astype(float)
            p = float(np.mean(intervals))
        else:
            p = float(len(y))

        z = float(np.mean(y[non_zero_indices]))
        last_non_zero = non_zero_indices[0]

        demand_sizes = list(y[non_zero_indices])

        for t in range(non_zero_indices[0] + 1, len(y)):
            if y[t] > 0:
                interval = float(t - last_non_zero)
                z = self.alpha * y[t] + (1 - self.alpha) * z
                p = self.alpha * interval + (1 - self.alpha) * p
                last_non_zero = t
                demand_sizes.append(y[t])

        # Compute expected demand rate per period
        rate = z / p if p > 0 else z
        if self.use_sba:
            # Syntetos-Boylan debiasing adjustment: (1 - alpha / 2)
            rate = (1.0 - (self.alpha / 2.0)) * rate

        self.demand_rate = max(0.0, float(rate))
        self.std_demand = float(np.std(demand_sizes)) if len(demand_sizes) > 1 else 0.5
        self.fitted = True
        return self

    def predict(self, horizon_days: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        if not self.fitted:
            raise RuntimeError("Model must be fit before predict() can be called.")
        point = np.full(horizon_days, self.demand_rate)
        lower = np.maximum(0.0, point - 1.282 * self.std_demand)
        upper = point + 1.282 * self.std_demand
        return point, lower, upper
