from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QMouseEvent, QPainter, QPen, QRegion
from PySide6.QtWidgets import QWidget

from app.capture.region import paint_selection_border


class RegionFrame(QWidget):
    """Always-on-top capture frame: resize by edges/corners, move by the top edge."""

    region_changed = Signal(QRect)

    MARGIN = 10
    MIN_SIZE = QSize(40, 24)
    HANDLE = 8
    HANDLE_FILL = QColor(255, 255, 255)
    HANDLE_EDGE = QColor(90, 102, 120)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self._region = QRect()
        self._mode = ""
        self._press_global = QPoint()
        self._press_region = QRect()

    def set_region(self, rect: QRect) -> None:
        self._region = QRect(rect)
        if self._region.width() < self.MIN_SIZE.width():
            self._region.setWidth(self.MIN_SIZE.width())
        if self._region.height() < self.MIN_SIZE.height():
            self._region.setHeight(self.MIN_SIZE.height())
        self._sync_geometry()
        self.show()
        self.raise_()

    def region(self) -> QRect:
        return QRect(self._region)

    def is_dragging(self) -> bool:
        return bool(self._mode)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._mode = self._hit(event.position().toPoint())
        self._press_global = event.globalPosition().toPoint()
        self._press_region = QRect(self._region)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        if event.buttons() & Qt.MouseButton.LeftButton and self._mode:
            self._apply_drag(event.globalPosition().toPoint())
            return
        self.setCursor(_cursor_for(self._hit(pos)))

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._mode:
            self._mode = ""
            self.region_changed.emit(QRect(self._region))

    def leaveEvent(self, event) -> None:
        self.unsetCursor()
        super().leaveEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_mask()

    def paintEvent(self, event) -> None:
        inner = self._inner_rect()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        paint_selection_border(painter, inner)
        for handle in self._handles(inner):
            painter.setBrush(self.HANDLE_FILL)
            painter.setPen(QPen(self.HANDLE_EDGE, 1))
            painter.drawEllipse(handle)

    def _apply_drag(self, global_pos: QPoint) -> None:
        delta = global_pos - self._press_global
        rect = QRect(self._press_region)
        mode = self._mode
        if mode == "move":
            rect.translate(delta)
        else:
            if "l" in mode:
                rect.setLeft(rect.left() + delta.x())
            if "r" in mode:
                rect.setRight(rect.right() + delta.x())
            if "t" in mode:
                rect.setTop(rect.top() + delta.y())
            if "b" in mode:
                rect.setBottom(rect.bottom() + delta.y())
            rect = _clamp_min(rect.normalized(), self.MIN_SIZE)
        self._region = rect
        self._sync_geometry()
        self.region_changed.emit(QRect(self._region))

    def _sync_geometry(self) -> None:
        m = self.MARGIN
        self.setGeometry(self._region.adjusted(-m, -m, m, m))
        self._update_mask()
        self.update()

    def _update_mask(self) -> None:
        inner = self._inner_rect()
        hole = inner.adjusted(4, 4, -4, -4)
        if hole.width() <= 0 or hole.height() <= 0:
            self.clearMask()
            return
        self.setMask(QRegion(self.rect()) - QRegion(hole))

    def _inner_rect(self) -> QRect:
        m = self.MARGIN
        return self.rect().adjusted(m, m, -m, -m)

    def _hit(self, pos: QPoint) -> str:
        m = self.MARGIN
        r = self.rect()
        left = pos.x() <= m
        right = pos.x() >= r.width() - m
        top = pos.y() <= m
        bottom = pos.y() >= r.height() - m
        if top and left:
            return "tl"
        if top and right:
            return "tr"
        if bottom and left:
            return "bl"
        if bottom and right:
            return "br"
        if left:
            return "l"
        if right:
            return "r"
        if bottom:
            return "b"
        if top:
            return "move"
        return ""

    def _handles(self, inner: QRect) -> list[QRect]:
        s = self.HANDLE
        cx = inner.center().x() - s // 2
        cy = inner.center().y() - s // 2
        return [
            QRect(inner.left() - s, inner.top() - s, s, s),
            QRect(cx, inner.top() - s, s, s),
            QRect(inner.right(), inner.top() - s, s, s),
            QRect(inner.left() - s, cy, s, s),
            QRect(inner.right(), cy, s, s),
            QRect(inner.left() - s, inner.bottom(), s, s),
            QRect(cx, inner.bottom(), s, s),
            QRect(inner.right(), inner.bottom(), s, s),
        ]


def _clamp_min(rect: QRect, minimum: QSize) -> QRect:
    if rect.width() < minimum.width():
        rect.setWidth(minimum.width())
    if rect.height() < minimum.height():
        rect.setHeight(minimum.height())
    return rect


def _cursor_for(mode: str) -> QCursor:
    mapping = {
        "l": Qt.CursorShape.SizeHorCursor,
        "r": Qt.CursorShape.SizeHorCursor,
        "b": Qt.CursorShape.SizeVerCursor,
        "tl": Qt.CursorShape.SizeFDiagCursor,
        "br": Qt.CursorShape.SizeFDiagCursor,
        "tr": Qt.CursorShape.SizeBDiagCursor,
        "bl": Qt.CursorShape.SizeBDiagCursor,
        "move": Qt.CursorShape.SizeAllCursor,
    }
    return QCursor(mapping.get(mode, Qt.CursorShape.ArrowCursor))
