from __future__ import annotations

import ctypes

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QMouseEvent,
    QPainter,
    QPainterPath,
)
from PySide6.QtWidgets import QWidget

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080

WRAP_FLAGS = Qt.TextFlag.TextWordWrap | Qt.TextFlag.TextWrapAnywhere
PAD_X = 18
PAD_Y = 16
GAP = 8
GRIP_H = 26


class OverlayGrip(QWidget):
    """Separate handle so the subtitle can be dragged even when click-through is on."""

    moved = Signal(QPoint)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setFixedHeight(GRIP_H)
        self._drag_offset: QPoint | None = None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is None:
            return
        self.moved.emit(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_offset = None

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.rect().adjusted(1, 1, -1, -1), 10, 10)
        painter.fillPath(path, QColor(245, 184, 76))
        painter.setPen(QColor(90, 70, 20))
        painter.setFont(QFont("Microsoft YaHei UI", 10, QFont.Weight.DemiBold))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "拖动移动字幕")


class OverlayWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._original = "框选区域后点击开始"
        self._translated = "字幕会显示在这里"
        self._is_error = False
        self._show_original = True
        self._font_size = 22
        self._opacity = 0.78
        self._click_through = True
        self._drag_offset: QPoint | None = None
        self._follow_rect = QRect()
        self._pinned = False
        self._grip = OverlayGrip()
        self._grip.moved.connect(self._on_grip_moved)
        self.resize(520, 120)

    def set_texts(self, original: str, translated: str, is_error: bool = False) -> None:
        self._original = original or ""
        self._translated = translated or ""
        self._is_error = is_error
        self._relayout()
        if not self._pinned:
            self._place()
        self._sync_grip()
        self.update()

    def set_show_original(self, enabled: bool) -> None:
        self._show_original = enabled
        self._relayout()
        if not self._pinned:
            self._place()
        self._sync_grip()
        self.update()

    def set_font_size(self, size: int) -> None:
        self._font_size = max(12, size)
        self._relayout()
        if not self._pinned:
            self._place()
        self._sync_grip()
        self.update()

    def set_opacity(self, value: float) -> None:
        self._opacity = min(0.95, max(0.35, value))
        self.update()

    def set_click_through(self, enabled: bool) -> None:
        self._click_through = enabled
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, enabled)
        self._apply_win_click_through(enabled)

    def follow_region(self, rect: QRect, force: bool = False) -> None:
        self._follow_rect = QRect(rect)
        available = _available(rect)
        width = min(max(rect.width(), 420), max(available.width() - 24, 280))
        self._relayout(width)
        if force:
            self._pinned = False
        if force or not self._pinned:
            self._place()
        self._sync_grip()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._click_through or event.button() != Qt.MouseButton.LeftButton:
            return
        self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is None:
            return
        self._move_pinned(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_offset = None

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._apply_win_click_through(self._click_through)
        self._sync_grip()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._grip.hide()

    def closeEvent(self, event) -> None:
        self._grip.close()
        super().closeEvent(event)

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        self._sync_grip()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_grip()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.rect().adjusted(1, 1, -1, -1), 14, 14)
        fill = QColor(255, 255, 255, int(255 * self._opacity))
        painter.fillPath(path, fill)
        painter.setPen(QColor(212, 168, 72, 180))
        painter.drawPath(path)

        left, top, width = PAD_X, PAD_Y, max(self.width() - PAD_X * 2, 40)
        if self._show_original and self._original:
            painter.setPen(QColor(90, 96, 108))
            painter.setFont(self._orig_font())
            orig_rect = QRect(left, top, width, _text_size(self._original, self._orig_font(), width).height())
            painter.drawText(orig_rect, WRAP_FLAGS, self._original)
            top = orig_rect.bottom() + GAP

        color = QColor(196, 57, 48) if self._is_error else QColor(22, 24, 28)
        painter.setPen(color)
        painter.setFont(self._trans_font())
        text = self._translated or "…"
        trans_rect = QRect(left, top, width, max(self.height() - top - PAD_Y, 20))
        painter.drawText(trans_rect, WRAP_FLAGS, text)

    def _orig_font(self) -> QFont:
        return QFont("Microsoft YaHei UI", max(11, self._font_size - 8))

    def _trans_font(self) -> QFont:
        return QFont("Microsoft YaHei UI", self._font_size, QFont.Weight.DemiBold)

    def _on_grip_moved(self, top_left: QPoint) -> None:
        available = _available(self._follow_rect if self._follow_rect.isValid() else self.geometry())
        grip_h = self._grip.height()
        x = min(max(top_left.x(), available.x() + 8), available.right() - self.width() - 8)
        overlay_y = top_left.y() + grip_h
        overlay_y = min(max(overlay_y, available.y() + 8), available.bottom() - self.height() - 8)
        self._move_pinned(QPoint(x, overlay_y))

    def _move_pinned(self, pos: QPoint) -> None:
        self._pinned = True
        self.move(pos)
        self._sync_grip()

    def _relayout(self, width: int | None = None) -> None:
        available = _available(self._follow_rect if self._follow_rect.isValid() else self.geometry())
        width = width or max(self.width(), 420)
        width = min(max(width, 280), max(available.width() - 24, 280))
        content_w = max(width - PAD_X * 2, 40)
        height = PAD_Y
        if self._show_original and self._original:
            height += _text_size(self._original, self._orig_font(), content_w).height() + GAP
        height += _text_size(self._translated or "…", self._trans_font(), content_w).height()
        height += PAD_Y
        max_h = max(available.height() - 24, 72)
        self.resize(width, min(max(height, 72), max_h))

    def _place(self) -> None:
        rect = self._follow_rect
        if not rect.isValid() or rect.width() < 1:
            return
        available = _available(rect)
        x = min(max(rect.x(), available.x() + 8), available.right() - self.width() - 8)
        y = rect.y() + rect.height() + 18
        if y + self.height() > available.bottom() - 8:
            y = rect.y() - self.height() - GRIP_H - 8
        y = min(max(y, available.y() + GRIP_H + 8), available.bottom() - self.height() - 8)
        self.move(x, y)
        self._sync_grip()

    def _sync_grip(self) -> None:
        if not self.isVisible():
            self._grip.hide()
            return
        available = _available(self.geometry())
        gy = self.y() - GRIP_H - 2
        if gy < available.y() + 4:
            gy = self.y() + 4
        self._grip.setFixedWidth(max(self.width(), 160))
        self._grip.move(self.x(), gy)
        self._grip.show()
        self._grip.raise_()

    def _apply_win_click_through(self, enabled: bool) -> None:
        try:
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            extra = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            extra |= WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
            if enabled:
                extra |= WS_EX_TRANSPARENT
            else:
                extra &= ~WS_EX_TRANSPARENT
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, extra)
        except Exception:
            pass


def _available(rect: QRect) -> QRect:
    screen = QGuiApplication.screenAt(rect.center()) or QGuiApplication.primaryScreen()
    if screen is None:
        return QRect(0, 0, 1920, 1080)
    return screen.availableGeometry()


def _text_size(text: str, font: QFont, width: int) -> QSize:
    metrics = QFontMetrics(font)
    bounds = metrics.boundingRect(0, 0, max(width, 40), 20000, WRAP_FLAGS, text or " ")
    return QSize(max(bounds.width(), 1), max(bounds.height() + metrics.descent(), font.pointSize() + 8))
