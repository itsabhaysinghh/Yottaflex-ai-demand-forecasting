from typing import Tuple
import numpy as np
from app.engines.forecasting.base import BaseForecaster


class ExponentialSmoothingForecaster(BaseForecaster):
    """
    Holt-Winters / Exponential Smoothing with level and weekly seasonality.
    """

    def __init__(self, alpha: float = 0.25, gamma: float = 0.15, season_length: int = 7):
        super().__init__(name="exponential_smoothing")
        self.alpha = alpha
        self.gamma = gamma
        self.season_length = season_length
        self.params = {"alpha": alpha, "gamma": gamma, "season_length": season_length}
        self.level = 0.0
        self.seasonals = np.ones(season_length)
        self.std_demand = 0.5
        self.observations_count = 0

    def fit(self, y: np.ndarray, **kwargs) -> "ExponentialSmoothingForecaster":
        y = np.asarray(y, dtype=float)
        self.observations_count = len(y)
        L = self.season_length
        if len(y) < L * 2:
            # Fallback to simple exponential smoothing when series is short
            self.level = float(y[-1]) if len(y) > 0 else 0.0
            self.seasonals = np.ones(L)
            self.std_demand = float(np.std(y)) if len(y) > 1 else 0.5
            self.fitted = True
            return self

        # Initialize level and additive seasonal components
        initial_level = float(np.mean(y[:L]))
        seasonals = np.zeros(L)
        for i in range(L):
            seasonals[i] = y[i] - initial_level

        level = initial_level
        for t in range(L, len(y)):
            val = y[t]
            s_idx = t % L
            prev_level = level
            level = self.alpha * (val - seasonals[s_idx]) + (1 - self.alpha) * prev_level
            seasonals[s_idx] = self.gamma * (val - level) + (1 - self.gamma) * seasonals[s_idx]

        self.level = float(level)
        self.seasonals = seasonals
        self.std_demand = float(np.std(y[-L*2:])) if len(y) >= L*2 else 0.5
        self.fitted = True
        return self

    def predict(self, horizon_days: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        if not self.fitted:
            raise RuntimeError("Model must be fit before predict() can be called.")
        L = self.season_length
        point = np.zeros(horizon_days)
        for h in range(horizon_days):
            s_idx = (self.observations_count + h) % L
            point[h] = max(0.0, self.level + self.seasonals[s_idx])

        lower = np.maximum(0.0, point - 1.282 * self.std_demand)
        upper = point + 1.282 * self.std_demand
        return point, lower, upper

