from __future__ import annotations
import numpy as np
from collections import deque
from typing import Deque, Tuple

from app.config import AppConfig
from app.services.thermal_adapters import ThermalFrame


class DeceptionService:
    def __init__(self, config: AppConfig):
        self.config = config
        self.history: Deque[Tuple[float, float]] = deque(maxlen=120)
        self.current_label = "Правда"

    def _extract_features(self, frame: ThermalFrame) -> np.ndarray:
        img = frame.temperature_matrix if frame.temperature_matrix is not None else frame.frame
        gray = img if len(img.shape) == 2 else np.mean(img, axis=2)
        center_slice = gray[gray.shape[0] // 4 : gray.shape[0] * 3 // 4, gray.shape[1] // 4 : gray.shape[1] * 3 // 4]
        mean_val = float(np.mean(center_slice))
        std_val = float(np.std(center_slice))
        gradient = float(np.mean(np.abs(np.gradient(center_slice))))
        return np.array([mean_val, std_val, gradient], dtype=float)

    def infer(self, frame: ThermalFrame, timestamp_ms: int) -> tuple[str, float]:
        feats = self._extract_features(frame)
        weights = np.array(self.config.weights)
        z = float(np.dot(feats, weights) + self.config.bias)
        p = 1.0 / (1.0 + np.exp(-z))
        self.history.append((timestamp_ms, p))
        self._update_label(p)
        return self.current_label, p

    def _update_label(self, p: float):
        if p >= self.config.threshold_hi:
            self.current_label = "Ложь"
        elif p <= self.config.threshold_lo:
            self.current_label = "Правда"
        # otherwise hold previous value

    def export_history(self):
        return list(self.history)
