from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QRect, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QScreen
from PySide6.QtWidgets import QWidget

from app.capture.dpi import apply_native_screen_cover, physical_to_qrect, qrect_to_physical

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
GA_ROOT = 2

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


user32.WindowFromPoint.restype = wintypes.HWND
user32.WindowFromPoint.argtypes = [_POINT]
user32.GetAncestor.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, ctypes.c_uint]
user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.c_void_p]
user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.c_void_p]
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


def exe_key(path: str) -> str:
    return Path(path).name.lower() if path else ""


def region_to_rel(region: QRect, client: QRect) -> list[float]:
    width = max(client.width(), 1)
    height = max(client.height(), 1)
    return [
        (region.x() - client.x()) / width,
        (region.y() - client.y()) / height,
        region.width() / width,
        region.height() / height,
    ]


def rel_to_region(rel: list[float], client: QRect) -> QRect:
    if len(rel) != 4:
        return QRect()
    nx, ny, nw, nh = (float(v) for v in rel)
    return QRect(
        client.x() + round(nx * client.width()),
        client.y() + round(ny * client.height()),
        max(8, round(nw * client.width())),
        max(8, round(nh * client.height())),
    )


def process_image_path(pid: int) -> str:
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(32768)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return buf.value
    finally:
        kernel32.CloseHandle(handle)
    return ""


def hwnd_pid(hwnd: int) -> int:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


def hwnd_exe_path(hwnd: int) -> str:
    return process_image_path(hwnd_pid(hwnd))


def client_qrect(hwnd: int) -> QRect | None:
    if not hwnd:
        return None
    area = _RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(area)):
        return None
    top_left = _POINT(area.left, area.top)
    bottom_right = _POINT(area.right, area.bottom)
    if not user32.ClientToScreen(hwnd, ctypes.byref(top_left)):
        return None
    if not user32.ClientToScreen(hwnd, ctypes.byref(bottom_right)):
        return None
    width = bottom_right.x - top_left.x
    height = bottom_right.y - top_left.y
    if width < 8 or height < 8:
        return None
    return physical_to_qrect(top_left.x, top_left.y, width, height)


def window_at_point(qt_global: QPoint, exclude_pid: int | None = None) -> tuple[int, str]:
    if exclude_pid is None:
        exclude_pid = os.getpid()
    phys = qrect_to_physical(QRect(qt_global.x(), qt_global.y(), 1, 1))
    hwnd = user32.WindowFromPoint(_POINT(phys[0], phys[1]))
    if hwnd:
        root = user32.GetAncestor(hwnd, GA_ROOT) or hwnd
        hwnd = int(root)
        if hwnd_pid(hwnd) != exclude_pid:
            path = hwnd_exe_path(hwnd)
            if path:
                return hwnd, path
    return _best_window_containing(qt_global, exclude_pid)


def find_window_for_exe(exe_path: str) -> tuple[int, QRect] | None:
    key = exe_key(exe_path)
    if not key:
        return None
    best: tuple[int, QRect, int] | None = None
    for hwnd in _top_windows():
        if hwnd_pid(hwnd) == os.getpid():
            continue
        path = hwnd_exe_path(hwnd)
        if exe_key(path) != key:
            continue
        client = client_qrect(hwnd)
        if client is None:
            continue
        area = client.width() * client.height()
        if best is None or area > best[2]:
            best = (hwnd, client, area)
    if best is None:
        return None
    return best[0], best[1]


def resolve_bound_window(exe_path: str, preferred_hwnd: int = 0) -> tuple[int, QRect] | None:
    if preferred_hwnd and user32.IsWindow(preferred_hwnd) and not user32.IsIconic(preferred_hwnd):
        if not exe_path or exe_key(hwnd_exe_path(preferred_hwnd)) == exe_key(exe_path):
            client = client_qrect(preferred_hwnd)
            if client is not None:
                return preferred_hwnd, client
    return find_window_for_exe(exe_path)


class WindowPicker(QObject):
    picked = Signal(int, str)
    cancelled = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._masks: list[_PickMask] = []

    def start(self) -> None:
        self.close()
        for screen in QGuiApplication.screens():
            mask = _PickMask(screen)
            mask.clicked.connect(self._on_clicked)
            mask.cancelled.connect(self._on_cancelled)
            self._masks.append(mask)
            mask.begin()

    def close(self) -> None:
        for mask in self._masks:
            mask.hide()
            mask.deleteLater()
        self._masks.clear()

    def _on_clicked(self, pos: QPoint) -> None:
        self.close()
        QTimer.singleShot(50, lambda: self._emit_pick(QPoint(pos)))

    def _emit_pick(self, pos: QPoint) -> None:
        hwnd, path = window_at_point(pos)
        if hwnd and path:
            self.picked.emit(hwnd, path)
        else:
            self.cancelled.emit()

    def _on_cancelled(self) -> None:
        self.close()
        self.cancelled.emit()


class _PickMask(QWidget):
    clicked = Signal(QPoint)
    cancelled = Signal()

    def __init__(self, screen: QScreen) -> None:
        super().__init__()
        self._screen = screen
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def begin(self) -> None:
        self.setGeometry(self._screen.geometry())
        handle = self.windowHandle()
        if handle is not None:
            handle.setScreen(self._screen)
        self.show()
        self.raise_()
        try:
            apply_native_screen_cover(int(self.winId()), self._screen)
        except Exception:
            pass
        self.activateWindow()
        self.setFocus()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(event.globalPosition().toPoint())

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(8, 12, 20, 90))
        painter.setPen(QColor(255, 255, 255, 230))
        painter.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignCenter,
            "点击要绑定的窗口，Esc 取消",
        )


def _top_windows() -> list[int]:
    found: list[int] = []

    def _callback(hwnd: int, _lparam: int) -> bool:
        if user32.IsWindowVisible(hwnd) and not user32.IsIconic(hwnd):
            found.append(int(hwnd))
        return True

    cb = WNDENUMPROC(_callback)
    user32.EnumWindows(cb, 0)
    return found


def _best_window_containing(qt_global: QPoint, exclude_pid: int) -> tuple[int, str]:
    best: tuple[int, str, int] | None = None
    for hwnd in _top_windows():
        if hwnd_pid(hwnd) == exclude_pid:
            continue
        client = client_qrect(hwnd)
        if client is None or not client.contains(qt_global):
            continue
        path = hwnd_exe_path(hwnd)
        if not path:
            continue
        area = client.width() * client.height()
        if best is None or area < best[2]:
            best = (hwnd, path, area)
    if best is None:
        return 0, ""
    return best[0], best[1]
