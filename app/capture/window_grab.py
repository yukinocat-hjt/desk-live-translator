from __future__ import annotations

import ctypes
from ctypes import wintypes

import numpy as np

from app.capture.window_bind import user32

PW_RENDERFULLCONTENT = 2
SRCCOPY = 0x00CC0020
DIB_RGB_COLORS = 0
BI_RGB = 0

gdi32 = ctypes.windll.gdi32


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", _BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.c_void_p]
user32.GetWindowDC.argtypes = [wintypes.HWND]
user32.GetWindowDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, ctypes.c_uint]
user32.PrintWindow.restype = wintypes.BOOL
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.BitBlt.argtypes = [
    wintypes.HDC,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HDC,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.DWORD,
]
gdi32.GetDIBits.argtypes = [
    wintypes.HDC,
    wintypes.HBITMAP,
    wintypes.UINT,
    wintypes.UINT,
    ctypes.c_void_p,
    ctypes.c_void_p,
    wintypes.UINT,
]
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wintypes.HDC]


def grab_window_region(hwnd: int, rel: list[float]) -> np.ndarray | None:
    """Capture a client-relative ROI from a window, even if another window covers it."""
    if not hwnd or len(rel) != 4 or not user32.IsWindow(hwnd) or user32.IsIconic(hwnd):
        return None
    image = _print_window(hwnd)
    if image is None or image.size == 0:
        return None
    crop = _crop_client_rel(hwnd, image, rel)
    if crop is None or crop.shape[0] < 2 or crop.shape[1] < 2:
        return None
    return np.ascontiguousarray(crop)


def _print_window(hwnd: int) -> np.ndarray | None:
    area = _RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(area)):
        return None
    width = int(area.right - area.left)
    height = int(area.bottom - area.top)
    if width < 8 or height < 8:
        return None
    hdc_win = user32.GetWindowDC(hwnd)
    if not hdc_win:
        return None
    hdc_mem = gdi32.CreateCompatibleDC(hdc_win)
    hbmp = gdi32.CreateCompatibleBitmap(hdc_win, width, height)
    if not hdc_mem or not hbmp:
        if hbmp:
            gdi32.DeleteObject(hbmp)
        if hdc_mem:
            gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(hwnd, hdc_win)
        return None
    old = gdi32.SelectObject(hdc_mem, hbmp)
    painted = user32.PrintWindow(hwnd, hdc_mem, PW_RENDERFULLCONTENT)
    if not painted:
        painted = user32.PrintWindow(hwnd, hdc_mem, 0)
    if not painted:
        gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_win, 0, 0, SRCCOPY)
    image = _bitmap_bgr(hdc_mem, hbmp, width, height)
    gdi32.SelectObject(hdc_mem, old)
    gdi32.DeleteObject(hbmp)
    gdi32.DeleteDC(hdc_mem)
    user32.ReleaseDC(hwnd, hdc_win)
    if image is None or int(image.max()) == 0:
        return None
    return image


def _crop_client_rel(hwnd: int, image: np.ndarray, rel: list[float]) -> np.ndarray | None:
    win = _RECT()
    client = _RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(win)):
        return None
    if not user32.GetClientRect(hwnd, ctypes.byref(client)):
        return None
    origin = _POINT(0, 0)
    if not user32.ClientToScreen(hwnd, ctypes.byref(origin)):
        return None
    ox = int(origin.x - win.left)
    oy = int(origin.y - win.top)
    cw = max(1, int(client.right - client.left))
    ch = max(1, int(client.bottom - client.top))
    nx, ny, nw, nh = (float(v) for v in rel)
    left = ox + int(round(nx * cw))
    top = oy + int(round(ny * ch))
    width = max(2, int(round(nw * cw)))
    height = max(2, int(round(nh * ch)))
    img_h, img_w = image.shape[:2]
    left = min(max(0, left), img_w - 2)
    top = min(max(0, top), img_h - 2)
    right = min(img_w, left + width)
    bottom = min(img_h, top + height)
    if right - left < 2 or bottom - top < 2:
        return None
    return image[top:bottom, left:right]


def _bitmap_bgr(hdc, hbmp, width: int, height: int) -> np.ndarray | None:
    info = _BITMAPINFO()
    info.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
    info.bmiHeader.biWidth = width
    info.bmiHeader.biHeight = -height
    info.bmiHeader.biPlanes = 1
    info.bmiHeader.biBitCount = 32
    info.bmiHeader.biCompression = BI_RGB
    buf = (ctypes.c_ubyte * (width * height * 4))()
    copied = gdi32.GetDIBits(hdc, hbmp, 0, height, buf, ctypes.byref(info), DIB_RGB_COLORS)
    if copied == 0:
        return None
    bgra = np.frombuffer(buf, dtype=np.uint8).reshape(height, width, 4)
    return np.ascontiguousarray(bgra[:, :, :3])
