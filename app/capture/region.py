from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget


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


class RegionSelector(QWidget):
    """Fullscreen translucent mask; drag a rectangle to pick the OCR region."""

    selected = Signal(QRect)
    cancelled = Signal()

    def __init__(self) -> None:
        super().__init__()
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
        geo = QGuiApplication.primaryScreen().virtualGeometry()
        self.setGeometry(geo)

    def start(self) -> None:
        self._origin = None
        self._current = None
        geo = QGuiApplication.primaryScreen().virtualGeometry()
        self.setGeometry(geo)
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._origin = event.position().toPoint()
            self._current = self._origin
            self.update()

    def mouseMoveEvent(self, event) -> None:
        if self._origin is not None:
            self._current = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._origin is None:
            return
        self._current = event.position().toPoint()
        rect = self._selection()
        self.hide()
        if rect.width() >= 8 and rect.height() >= 8:
            self.selected.emit(self._to_global(rect))
        else:
            self.cancelled.emit()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            self.cancelled.emit()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            rect = self._selection()
            self.hide()
            if rect.width() >= 8 and rect.height() >= 8:
                self.selected.emit(self._to_global(rect))
            else:
                self.cancelled.emit()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(8, 12, 20, 120))
        sel = self._selection()
        if sel.width() > 2 and sel.height() > 2:
            hole = sel.adjusted(3, 3, -3, -3)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(hole, Qt.GlobalColor.transparent)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            paint_selection_border(painter, sel)

    def _selection(self) -> QRect:
        if self._origin is None or self._current is None:
            return QRect()
        return QRect(self._origin, self._current).normalized()

    def _to_global(self, rect: QRect) -> QRect:
        top_left = self.mapToGlobal(rect.topLeft())
        return QRect(top_left, rect.size())
