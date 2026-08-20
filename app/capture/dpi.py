from __future__ import annotations

import ctypes
from ctypes import wintypes

from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication, QScreen


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class _MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", _RECT),
        ("rcWork", _RECT),
        ("dwFlags", wintypes.DWORD),
    ]


HWND_TOPMOST = -1
SWP_SHOWWINDOW = 0x0040
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)


def enable_per_monitor_dpi() -> None:
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
        return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def monitor_physical_rect(screen: QScreen) -> QRect:
    try:
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(_MONITORINFO)
        handle = int(screen.handle())
        if ctypes.windll.user32.GetMonitorInfoW(handle, ctypes.byref(info)):
            area = info.rcMonitor
            return QRect(area.left, area.top, area.right - area.left, area.bottom - area.top)
    except Exception:
        pass
    geo = screen.geometry()
    dpr = float(screen.devicePixelRatio())
    return QRect(
        round(geo.x() * dpr),
        round(geo.y() * dpr),
        max(1, round(geo.width() * dpr)),
        max(1, round(geo.height() * dpr)),
    )


def apply_native_screen_cover(hwnd: int, screen: QScreen) -> None:
    phys = monitor_physical_rect(screen)
    ctypes.windll.user32.SetWindowPos(
        hwnd,
        HWND_TOPMOST,
        phys.x(),
        phys.y(),
        phys.width(),
        phys.height(),
        SWP_SHOWWINDOW,
    )


def qrect_to_physical(rect: QRect) -> tuple[int, int, int, int]:
    screen = QGuiApplication.screenAt(rect.center()) or QGuiApplication.primaryScreen()
    if screen is None:
        return rect.x(), rect.y(), max(2, rect.width()), max(2, rect.height())
    geo = screen.geometry()
    phys = monitor_physical_rect(screen)
    scale_x = phys.width() / max(geo.width(), 1)
    scale_y = phys.height() / max(geo.height(), 1)
    left = phys.x() + round((rect.x() - geo.x()) * scale_x)
    top = phys.y() + round((rect.y() - geo.y()) * scale_y)
    width = max(2, round(rect.width() * scale_x))
    height = max(2, round(rect.height() * scale_y))
    return left, top, width, height


def physical_to_qrect(x: int, y: int, w: int, h: int) -> QRect:
    screen = None
    cx, cy = x + w // 2, y + h // 2
    for candidate in QGuiApplication.screens():
        phys = monitor_physical_rect(candidate)
        if phys.contains(cx, cy):
            screen = candidate
            break
    if screen is None:
        screen = QGuiApplication.primaryScreen()
    if screen is None:
        return QRect(x, y, max(1, w), max(1, h))
    geo = screen.geometry()
    phys = monitor_physical_rect(screen)
    scale_x = geo.width() / max(phys.width(), 1)
    scale_y = geo.height() / max(phys.height(), 1)
    left = geo.x() + round((x - phys.x()) * scale_x)
    top = geo.y() + round((y - phys.y()) * scale_y)
    return QRect(
        left,
        top,
        max(1, round(w * scale_x)),
        max(1, round(h * scale_y)),
    )
