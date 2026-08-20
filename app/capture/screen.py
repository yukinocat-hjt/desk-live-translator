from __future__ import annotations

from typing import Any

import numpy as np

from app.capture.dpi import qrect_to_physical

__all__ = ["ScreenCapturer", "qrect_to_physical"]


class ScreenCapturer:
    """Grab a screen ROI. Prefer DXGI (dxcam), fall back to mss."""

    def __init__(self) -> None:
        self._backend = "mss"
        self._camera: Any = None
        self._output_idx = 0
        self._output_origin = (0, 0)
        self._mss = None
        self._init_mss()
        self._try_init_dxcam()

    @property
    def backend(self) -> str:
        return self._backend

    def close(self) -> None:
        if self._camera is not None:
            try:
                self._camera.stop()
            except Exception:
                pass
            self._camera = None
        if self._mss is not None:
            try:
                self._mss.close()
            except Exception:
                pass
            self._mss = None

    def grab(self, x: int, y: int, w: int, h: int) -> np.ndarray | None:
        if w < 2 or h < 2:
            return None
        if self._backend == "dxcam":
            frame = self._grab_dxcam(x, y, w, h)
            if frame is not None:
                return frame
        return self._grab_mss(x, y, w, h)

    def _init_mss(self) -> None:
        import mss

        self._mss = mss.mss()

    def _try_init_dxcam(self) -> None:
        try:
            import dxcam

            camera = dxcam.create(output_idx=0, output_color="BGR")
            if camera is None:
                return
            self._camera = camera
            self._output_idx = 0
            self._output_origin = _monitor_origin(self._mss, 1)
            self._backend = "dxcam"
        except Exception:
            self._camera = None
            self._backend = "mss"

    def _grab_dxcam(self, x: int, y: int, w: int, h: int) -> np.ndarray | None:
        if self._camera is None:
            return None
        ox, oy = self._output_origin
        rel_l, rel_t = x - ox, y - oy
        rel_r, rel_b = rel_l + w, rel_t + h
        if rel_l < 0 or rel_t < 0:
            return None
        try:
            frame = self._camera.grab(region=(rel_l, rel_t, rel_r, rel_b))
        except Exception:
            self._backend = "mss"
            return None
        if frame is None:
            # dxcam returns None when the frame did not change; grab a mss snapshot instead
            return self._grab_mss(x, y, w, h)
        if frame.ndim == 3 and frame.shape[2] == 4:
            return np.ascontiguousarray(frame[:, :, :3])
        return np.ascontiguousarray(frame)

    def _grab_mss(self, x: int, y: int, w: int, h: int) -> np.ndarray | None:
        if self._mss is None:
            self._init_mss()
        assert self._mss is not None
        monitor = {"left": int(x), "top": int(y), "width": int(w), "height": int(h)}
        try:
            shot = self._mss.grab(monitor)
        except Exception:
            return None
        bgra = np.array(shot, dtype=np.uint8)
        if bgra.ndim != 3:
            return None
        return np.ascontiguousarray(bgra[:, :, :3])


def _monitor_origin(sct: Any, index: int) -> tuple[int, int]:
    if sct is None:
        return (0, 0)
    monitors = getattr(sct, "monitors", None)
    if not monitors or index >= len(monitors):
        return (0, 0)
    mon = monitors[index]
    return (int(mon.get("left", 0)), int(mon.get("top", 0)))
