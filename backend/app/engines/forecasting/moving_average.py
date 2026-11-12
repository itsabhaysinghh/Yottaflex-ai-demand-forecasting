from typing import Tuple
import numpy as np
from app.engines.forecasting.base import BaseForecaster


class MovingAverageForecaster(BaseForecaster):
    """
    Moving Average Forecaster supporting simple rolling window.
    """

    def __init__(self, window: int = 14):
        super().__init__(name="moving_average")
        self.window = window
        self.params = {"window": window}
        self.mean_demand = 0.0
        self.std_demand = 0.0

    def fit(self, y: np.ndarray, **kwargs) -> "MovingAverageForecaster":
        y = np.asarray(y, dtype=float)
        if len(y) == 0:
            self.mean_demand = 0.0
            self.std_demand = 0.0
        else:
            recent = y[-self.window:] if len(y) >= self.window else y
            self.mean_demand = float(np.mean(recent))
            self.std_demand = float(np.std(recent)) if len(recent) > 1 else 0.5
        self.fitted = True
        return self

    def predict(self, horizon_days: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        if not self.fitted:
            raise RuntimeError("Model must be fit before predict() can be called.")
        point = np.full(horizon_days, max(0.0, self.mean_demand))
        # 80% normal confidence interval: Z = 1.282
        lower = np.maximum(0.0, point - 1.282 * self.std_demand)
        upper = point + 1.282 * self.std_demand
        return point, lower, upper

