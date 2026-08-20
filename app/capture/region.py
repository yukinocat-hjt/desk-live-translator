from __future__ import annotations

from PySide6.QtCore import QObject, QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen, QScreen
from PySide6.QtWidgets import QWidget

from app.capture.dpi import apply_native_screen_cover


def paint_selection_border(painter: QPainter, rect: QRect) -> None:
    """Draw the marquee on the outer edge so right/bottom are not clipped."""
    box = QRectF(rect).adjusted(-1.5, -1.5, 1.5, 1.5)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    outline = QPen(QColor(255, 255, 255, 230), 3)
    outline.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    outline.setCapStyle(Qt.PenCapStyle.SquareCap)
    painter.setPen(outline)
    painter.drawRoundedRect(box, 3, 3)
    dash = QPen(QColor(90, 102, 120), 2)
    dash.setStyle(Qt.PenStyle.CustomDashLine)
    dash.setDashPattern([5, 4])
    dash.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    dash.setCapStyle(Qt.PenCapStyle.FlatCap)
    painter.setPen(dash)
    painter.drawRoundedRect(box, 3, 3)


class RegionSelector(QObject):
    """One fullscreen mask per monitor so 4K / DPI scaling cannot clip the selector."""

    selected = Signal(QRect)
    cancelled = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._masks: list[_ScreenMask] = []

    def start(self) -> None:
        self.close()
        for screen in QGuiApplication.screens():
            mask = _ScreenMask(screen)
            mask.selected.connect(self._on_selected)
            mask.cancelled.connect(self._on_cancelled)
            self._masks.append(mask)
            mask.begin()

    def close(self) -> None:
        for mask in self._masks:
            mask.hide()
            mask.deleteLater()
        self._masks.clear()

    def _on_selected(self, rect: QRect) -> None:
        self.close()
        self.selected.emit(rect)

    def _on_cancelled(self) -> None:
        self.close()
        self.cancelled.emit()


class _ScreenMask(QWidget):
    selected = Signal(QRect)
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
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._origin: QPoint | None = None
        self._current: QPoint | None = None

    def begin(self) -> None:
        self._origin = None
        self._current = None
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
            self._origin = event.globalPosition().toPoint()
            self._current = self._origin
            self.grabMouse()
            self.update()

    def mouseMoveEvent(self, event) -> None:
        if self._origin is not None:
            self._current = event.globalPosition().toPoint()
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._origin is None:
            return
        self._current = event.globalPosition().toPoint()
        self.releaseMouse()
        rect = self._selection_global()
        if rect.width() >= 8 and rect.height() >= 8:
            self.selected.emit(rect)
        else:
            self.cancelled.emit()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.releaseMouse()
            self.cancelled.emit()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.releaseMouse()
            rect = self._selection_global()
            if rect.width() >= 8 and rect.height() >= 8:
                self.selected.emit(rect)
            else:
                self.cancelled.emit()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(8, 12, 20, 120))
        sel = self._selection_local()
        if sel.width() > 2 and sel.height() > 2:
            hole = sel.adjusted(3, 3, -3, -3)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(hole, Qt.GlobalColor.transparent)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            paint_selection_border(painter, sel)

    def _selection_global(self) -> QRect:
        if self._origin is None or self._current is None:
            return QRect()
        return QRect(self._origin, self._current).normalized()

    def _selection_local(self) -> QRect:
        global_rect = self._selection_global()
        if not global_rect.isValid():
            return QRect()
        top_left = self.mapFromGlobal(global_rect.topLeft())
        return QRect(top_left, global_rect.size())
