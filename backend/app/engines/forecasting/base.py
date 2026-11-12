from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple
import numpy as np


class BaseForecaster(ABC):
    """
    Abstract base class for demand forecasting models.
    """

    def __init__(self, name: str):
        self.name = name
        self.params: Dict[str, Any] = {}
        self.fitted: bool = False

    @abstractmethod
    def fit(self, y: np.ndarray, **kwargs) -> "BaseForecaster":
        """
        Fits the model on historical demand values y.
        """
        pass

    @abstractmethod
    def predict(self, horizon_days: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Generates point forecasts, lower confidence bound (80%), and upper confidence bound (80%).
        Returns: (point_forecast, lower_bound, upper_bound)
        """
        pass

