from __future__ import annotations

import numpy as np


class ChangeDetector:
    """Downscale + grayscale diff. Local tiles catch small subtitle changes."""

    def __init__(self, threshold: float = 3.0, size: int = 96, tiles: int = 8) -> None:
        self.threshold = threshold
        self.size = size
        self.tiles = tiles
        self._prev: np.ndarray | None = None

    def reset(self) -> None:
        self._prev = None

    def changed(self, frame: np.ndarray) -> bool:
        small = _downscale_gray(frame, self.size)
        if self._prev is None:
            self._prev = small
            return True
        diff = np.abs(small.astype(np.float32) - self._prev.astype(np.float32))
        self._prev = small
        global_mean = float(np.mean(diff))
        if global_mean >= self.threshold:
            return True
        return _tile_max(diff, self.tiles) >= 10.0


def _tile_max(diff: np.ndarray, tiles: int) -> float:
    height, width = diff.shape[:2]
    tile_h, tile_w = height // tiles, width // tiles
    if tile_h < 1 or tile_w < 1:
        return float(np.mean(diff))
    cropped = diff[: tile_h * tiles, : tile_w * tiles]
    grid = cropped.reshape(tiles, tile_h, tiles, tile_w)
    return float(grid.mean(axis=(1, 3)).max())


def _downscale_gray(frame: np.ndarray, size: int) -> np.ndarray:
    import cv2

    if frame.ndim == 3 and frame.shape[2] >= 3:
        gray = cv2.cvtColor(frame[:, :, :3], cv2.COLOR_BGR2GRAY)
    else:
        gray = frame
    return cv2.resize(gray, (size, size), interpolation=cv2.INTER_AREA)
