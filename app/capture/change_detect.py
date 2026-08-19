from __future__ import annotations

import numpy as np


class ChangeDetector:
    """Downscale + grayscale mean-abs-diff to skip unchanged frames."""

    def __init__(self, threshold: float = 8.0, size: int = 64) -> None:
        self.threshold = threshold
        self.size = size
        self._prev: np.ndarray | None = None

    def reset(self) -> None:
        self._prev = None

    def changed(self, frame: np.ndarray) -> bool:
        small = _downscale_gray(frame, self.size)
        if self._prev is None:
            self._prev = small
            return True
        diff = float(np.mean(np.abs(small.astype(np.float32) - self._prev.astype(np.float32))))
        self._prev = small
        return diff >= self.threshold


def _downscale_gray(frame: np.ndarray, size: int) -> np.ndarray:
    import cv2

    if frame.ndim == 3 and frame.shape[2] >= 3:
        gray = cv2.cvtColor(frame[:, :, :3], cv2.COLOR_BGR2GRAY)
    else:
        gray = frame
    return cv2.resize(gray, (size, size), interpolation=cv2.INTER_AREA)
