from typing import Tuple
import numpy as np
from app.engines.forecasting.base import BaseForecaster


class SeasonalNaiveForecaster(BaseForecaster):
    """
    Seasonal Naive Forecaster repeating the exact seasonal pattern from the last cycle
    (default: season_length=7 for day-of-week retail seasonality).
    """

    def __init__(self, season_length: int = 7):
        super().__init__(name="seasonal_naive")
        self.season_length = season_length
        self.params = {"season_length": season_length}
        self.seasonal_pattern = np.zeros(season_length)
        self.std_demand = 0.0

    def fit(self, y: np.ndarray, **kwargs) -> "SeasonalNaiveForecaster":
        y = np.asarray(y, dtype=float)
        L = self.season_length
        if len(y) == 0:
            self.seasonal_pattern = np.zeros(L)
            self.std_demand = 0.5
        elif len(y) < L:
            # Repeat available mean across seasons
            m = np.mean(y)
            self.seasonal_pattern = np.full(L, m)
            self.std_demand = float(np.std(y)) if len(y) > 1 else 0.5
        else:
            self.seasonal_pattern = y[-L:].copy()
            self.std_demand = float(np.std(y[-min(len(y), 28):])) if len(y) > 1 else 0.5
        self.fitted = True
        return self

    def predict(self, horizon_days: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        if not self.fitted:
            raise RuntimeError("Model must be fit before predict() can be called.")
        L = self.season_length
        # Tile seasonal cycle over horizon
        repetitions = (horizon_days // L) + 1
        tiled = np.tile(self.seasonal_pattern, repetitions)[:horizon_days]
        point = np.maximum(0.0, tiled)
        lower = np.maximum(0.0, point - 1.282 * self.std_demand)
        upper = point + 1.282 * self.std_demand
        return point, lower, upper

