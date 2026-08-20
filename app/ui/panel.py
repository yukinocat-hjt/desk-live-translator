from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QCloseEvent, QColor, QFont, QFontDatabase, QPainter, QPen, QPixmap, QPolygonF, QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QMessageBox,
    QProxyStyle,
    QPushButton,
    QSlider,
    QStyle,
    QStyleFactory,
    QVBoxLayout,
    QWidget,
)

from app.capture.region import RegionSelector
from app.capture.window_bind import (
    WindowPicker,
    client_qrect,
    exe_key,
    find_window_for_exe,
    region_to_rel,
    rel_to_region,
    resolve_bound_window,
)
from app.config import AppConfig
from app.pipeline import Pipeline
from app.translate.base import LANG_LABELS
from app.ui.overlay import OverlayWindow
from app.ui.region_frame import RegionFrame

STYLESHEET = """
QWidget#Root {
    background: #ffffff;
    color: #1c212b;
    font-family: "Microsoft YaHei UI", "Segoe UI";
    font-size: 13px;
}
QLabel#Title {
    color: #141820;
    font-size: 22px;
    font-weight: 700;
}
QLabel#Subtitle, QLabel#Hint {
    color: #6b7280;
}
QLabel#Status {
    color: #9a6b12;
    font-weight: 600;
    padding: 6px 10px;
    background: #fff8ea;
    border: 1px solid #ead7a8;
    border-radius: 8px;
}
QFrame#Card {
    background: #f7f8fa;
    border: 1px solid #e4e7ec;
    border-radius: 14px;
}
QLineEdit, QComboBox {
    background: #ffffff;
    color: #1c212b;
    border: 1px solid #d5dae3;
    border-radius: 8px;
    padding: 6px 8px;
    min-height: 28px;
}
QComboBox {
    padding: 6px 32px 6px 12px;
}
QLineEdit:focus {
    border: 1px solid #f5b84c;
}
QComboBox:hover, QComboBox:focus, QComboBox:on {
    border: 1px solid #d5dae3;
    background: #ffffff;
}
QLineEdit:disabled, QComboBox:disabled {
    background: #f0f2f5;
    color: #9aa1ad;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 28px;
    border: none;
    background: transparent;
}
QComboBox::down-arrow {
    image: url("__ARROW__");
    width: 12px;
    height: 12px;
}
QComboBox:hover::down-arrow, QComboBox:on::down-arrow {
    image: url("__ARROW_ON__");
}
QComboBoxPrivateContainer {
    background: transparent;
    border: none;
    margin: 0;
    padding: 0;
}
QComboBoxPrivateScroller {
    max-height: 0;
    border: none;
    background: transparent;
}
QComboBox QAbstractItemView {
    background: #ffffff;
    color: #1c212b;
    border: none;
    border-radius: 10px;
    outline: 0;
    padding: 6px;
}
QComboBox QAbstractItemView::item {
    min-height: 32px;
    padding: 6px 12px;
    border: none;
    border-radius: 8px;
    color: #1c212b;
}
QComboBox QAbstractItemView QScrollBar:horizontal {
    height: 0px;
    border: none;
    background: transparent;
}
QComboBox QAbstractItemView::item:hover {
    background: #fff8ea;
    color: #141820;
}
QComboBox QAbstractItemView::item:selected {
    background: #f5b84c;
    color: #16120a;
}
QSlider::groove:horizontal {
    height: 6px;
    background: #e4e7ec;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    width: 16px;
    height: 16px;
    margin: -6px 0;
    background: #f5b84c;
    border-radius: 8px;
}
QCheckBox { spacing: 8px; color: #1c212b; }
QPushButton {
    background: #f5b84c;
    color: #16120a;
    border: none;
    border-radius: 10px;
    padding: 9px 16px;
    font-weight: 700;
}
QPushButton:hover { background: #ffd27a; }
QPushButton:disabled {
    background: #e8eaee;
    color: #9aa1ad;
}
QPushButton#Ghost {
    background: #eef0f4;
    color: #1c212b;
    font-weight: 600;
}
QPushButton#Ghost:hover { background: #e2e5eb; }
QPushButton#Danger {
    background: #fde8e6;
    color: #b42318;
}
QPushButton#Danger:hover { background: #f9d2ce; }
QPushButton#Danger:disabled {
    background: #f5e8e6;
    color: #c4a8a6;
}
QPushButton#SecretToggle {
    background: #eef0f4;
    color: #1c212b;
    font-weight: 600;
    padding: 6px 10px;
    min-width: 52px;
    border-radius: 8px;
}
QPushButton#SecretToggle:hover { background: #e2e5eb; }
QPushButton#SecretToggle:disabled {
    background: #e8eaee;
    color: #9aa1ad;
}
"""


class ControlPanel(QWidget):
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.setObjectName("Root")
        self.setWindowTitle("桌面实时翻译")
        self.setStyleSheet(
            STYLESHEET.replace("__ARROW__", _qss_url(_chevron_png("#5c5c5c", "chevron_down.png")))
            .replace("__ARROW_ON__", _qss_url(_chevron_png("#1a1a1a", "chevron_down_on.png")))
        )
        self.setMinimumWidth(520)
        self._config = config
        self._region = QRect()
        self._quitting = False
        self._running = False
        self._applying_bind = False
        self._bound_hwnd = 0
        self._saved_geometry: QRect | None = None

        self.overlay = OverlayWindow()
        self.frame = RegionFrame()
        self.selector = RegionSelector()
        self.window_picker = WindowPicker()
        self.pipeline = Pipeline()
        self._region_apply_timer = QTimer(self)
        self._region_apply_timer.setSingleShot(True)
        self._region_apply_timer.timeout.connect(self._apply_region_to_pipeline)
        self._bind_timer = QTimer(self)
        self._bind_timer.setInterval(250)
        self._bind_timer.timeout.connect(self._follow_bound_window)
        self.pipeline.result_ready.connect(self._on_result)
        self.pipeline.status_changed.connect(self._on_status)
        self.pipeline.finished.connect(self._on_pipeline_finished)
        self.selector.selected.connect(self._on_region_selected)
        self.selector.cancelled.connect(self._on_select_cancelled)
        self.window_picker.picked.connect(self._on_window_picked)
        self.window_picker.cancelled.connect(self._on_window_pick_cancelled)
        self.frame.region_changed.connect(self._on_region_resized)

        self._build_ui()
        self._load_fields()
        self.overlay.set_font_size(self._config.font_size)
        self.overlay.set_click_through(self._config.click_through)
        self._bind_timer.start()

    def toggle_run(self) -> None:
        if self._running:
            self.stop()
        else:
            self.start()

    def toggle_overlay(self) -> None:
        if self.overlay.isVisible():
            self.overlay.hide()
        else:
            self.overlay.show()

    def start_region_select(self) -> None:
        if self._running:
            self.stop()
        self._panel_was_visible = self.isVisible()
        self.overlay.hide()
        self.frame.hide()
        self._remember_geometry()
        self.window_picker.close()
        self.hide()
        QTimer.singleShot(160, self.selector.start)
        self._set_status("拖拽框选翻译区域")

    def _restore_panel_after_select(self) -> None:
        if not getattr(self, "_panel_was_visible", True):
            return
        self.showNormal()
        self._restore_geometry()
        self.raise_()
        self.activateWindow()

    def start_window_pick(self) -> None:
        self._panel_was_visible = self.isVisible()
        self.selector.close()
        self.overlay.hide()
        self.frame.hide()
        self._remember_geometry()
        self.hide()
        QTimer.singleShot(160, self.window_picker.start)
        self._set_status("点击要绑定的窗口")

    def _on_window_picked(self, hwnd: int, path: str) -> None:
        self._restore_panel_after_select()
        self._apply_bind(path, hwnd)
        if self._region.width() >= 8:
            self.frame.set_region(self._region)
            self.overlay.show()
        name = exe_key(path) or path
        self._set_status(f"已绑定 {name}，识别框跟随该窗口，并只截该窗口画面")

    def _on_window_pick_cancelled(self) -> None:
        self._restore_panel_after_select()
        if self._region.width() >= 8:
            self.frame.set_region(self._region)
            self.overlay.show()
        self._set_status("已取消绑定窗口")

    def _bind_exe_file(self) -> None:
        path, _checked = QFileDialog.getOpenFileName(
            self, "选择要绑定的程序", "", "程序 (*.exe)"
        )
        if not path:
            return
        found = find_window_for_exe(path)
        hwnd = found[0] if found else 0
        self._apply_bind(path, hwnd)
        name = exe_key(path) or path
        if hwnd:
            self._set_status(f"已绑定 {name}，识别框跟随该窗口，并只截该窗口画面")
        else:
            self._set_status(f"已绑定 {name}，程序运行后会自动跟随并只截该窗口")

    def _apply_bind(self, path: str, hwnd: int) -> None:
        self._config.bound_exe = path
        self._bound_hwnd = int(hwnd or 0)
        client = client_qrect(hwnd) if hwnd else None
        if client is None:
            found = resolve_bound_window(path, self._bound_hwnd)
            if found is not None:
                self._bound_hwnd, client = found
        if client is not None and self._region.width() >= 8:
            self._config.bound_rel = region_to_rel(self._region, client)
        self._config.save()
        self._refresh_bind_label()

    def _clear_bind(self) -> None:
        self._config.bound_exe = ""
        self._config.bound_rel = []
        self._bound_hwnd = 0
        self._config.save()
        self._refresh_bind_label()
        self._set_status("已取消绑定，识别区改回屏幕固定位置")

    def _sync_bound_rel_from_region(self) -> None:
        if not self._config.bound_exe or self._region.width() < 8:
            return
        found = resolve_bound_window(self._config.bound_exe, self._bound_hwnd)
        if found is None:
            return
        self._bound_hwnd, client = found
        self._config.bound_rel = region_to_rel(self._region, client)
        self._config.save()

    def _follow_bound_window(self) -> None:
        if not self._config.bound_exe:
            self._refresh_bind_label(running=None)
            return
        if self.frame.is_dragging():
            return
        found = resolve_bound_window(self._config.bound_exe, self._bound_hwnd)
        self._refresh_bind_label(running=found is not None)
        if found is None:
            self._bound_hwnd = 0
            return
        self._bound_hwnd, client = found
        if len(self._config.bound_rel) != 4:
            if self._region.width() >= 8:
                self._config.bound_rel = region_to_rel(self._region, client)
                self._config.save()
            return
        new_rect = rel_to_region(self._config.bound_rel, client)
        if new_rect.width() < 8 or new_rect.height() < 8:
            return
        if (
            abs(new_rect.x() - self._region.x()) < 2
            and abs(new_rect.y() - self._region.y()) < 2
            and abs(new_rect.width() - self._region.width()) < 2
            and abs(new_rect.height() - self._region.height()) < 2
        ):
            if self._running:
                self.pipeline.set_capture_hwnd(self._bound_hwnd)
            return
        self._applying_bind = True
        self._set_region(new_rect, apply_pipeline=self._running, snap_overlay=False)
        if self._region.width() >= 8:
            self.frame.set_region(new_rect)
        self._applying_bind = False

    def _refresh_bind_label(self, running: bool | None = None) -> None:
        path = self._config.bound_exe
        if not hasattr(self, "bind_label"):
            return
        if not path:
            self.bind_label.setText("未绑定")
            self.bind_clear_btn.setEnabled(False)
            return
        self.bind_clear_btn.setEnabled(True)
        name = exe_key(path) or path
        if running is None:
            running = resolve_bound_window(path, self._bound_hwnd) is not None
        state = "跟随中 · 仅该窗口" if running else "未运行"
        self.bind_label.setText(f"{name} · {state}")
        self.bind_label.setToolTip(path)

    def start(self) -> None:
        self._collect_fields()
        if self._region.width() < 8:
            self.start_region_select()
            return
        self._config.save()
        if self.pipeline.isRunning():
            self.pipeline.stop()
            self.pipeline.wait(2000)
        self.pipeline.configure(self._region, self._config, self._bound_hwnd)
        self.pipeline.start()
        self._running = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.overlay.follow_region(self._region)
        self.overlay.set_click_through(self._config.click_through)
        self.overlay.show()
        self.frame.set_region(self._region)
        if self._config.engine != "none" and not _has_keys(self._config):
            self._set_status("未配置 API Key，仅显示原文")
        else:
            self._set_status("正在启动…")

    def stop(self) -> None:
        self._running = False
        self.pipeline.stop()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._set_status("已暂停")

    def request_quit(self) -> None:
        self._quitting = True
        self.stop()
        if self.pipeline.isRunning():
            self.pipeline.wait(1500)
        self.overlay.close()
        self.frame.close()
        self.selector.close()
        self.window_picker.close()
        self._config.save()
        from PySide6.QtWidgets import QApplication

        QApplication.instance().quit()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._quitting:
            event.accept()
            return
        event.ignore()
        self._remember_geometry()
        self.hide()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if self._saved_geometry is not None:
            QTimer.singleShot(0, self._restore_geometry)

    def show_from_tray(self) -> None:
        self.showNormal()
        self._restore_geometry()
        self.raise_()
        self.activateWindow()

    def _remember_geometry(self) -> None:
        if not self.isVisible():
            return
        geo = self.normalGeometry() if self.isMaximized() else self.geometry()
        if geo.width() > 80 and geo.height() > 80:
            self._saved_geometry = QRect(geo)

    def _windowed_size(self) -> QSize:
        hint = self.sizeHint()
        width = max(self.minimumWidth(), min(hint.width(), 540))
        height = max(520, min(int(hint.height() * 0.88), 680))
        return QSize(width, height)

    def _restore_geometry(self) -> None:
        size = self._windowed_size()
        saved = self._saved_geometry
        x = saved.x() if saved is not None else self.x()
        y = saved.y() if saved is not None else self.y()
        self.setWindowState(Qt.WindowState.WindowNoState)
        self.setGeometry(x, y, size.width(), size.height())

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        title = QLabel("桌面实时翻译")
        title.setObjectName("Title")
        subtitle = QLabel("框选屏幕文字，本地 OCR，字幕层显示译文")
        subtitle.setObjectName("Subtitle")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles, 1)
        self.status_label = QLabel("就绪")
        self.status_label.setObjectName("Status")
        header.addWidget(self.status_label, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        card = QFrame()
        card.setObjectName("Card")
        form = QFormLayout(card)
        form.setContentsMargins(16, 14, 16, 14)
        form.setSpacing(10)

        region_row = QHBoxLayout()
        self.region_label = QLabel("尚未框选")
        self.region_btn = QPushButton("框选区域")
        self.region_btn.setObjectName("Ghost")
        self.region_btn.clicked.connect(self.start_region_select)
        region_row.addWidget(self.region_label, 1)
        region_row.addWidget(self.region_btn)
        form.addRow("识别区域", region_row)

        bind_row = QHBoxLayout()
        self.bind_label = QLabel("未绑定")
        self.bind_pick_btn = QPushButton("点选窗口")
        self.bind_pick_btn.setObjectName("Ghost")
        self.bind_pick_btn.clicked.connect(self.start_window_pick)
        self.bind_file_btn = QPushButton("选择程序")
        self.bind_file_btn.setObjectName("Ghost")
        self.bind_file_btn.clicked.connect(self._bind_exe_file)
        self.bind_clear_btn = QPushButton("取消绑定")
        self.bind_clear_btn.setObjectName("Ghost")
        self.bind_clear_btn.clicked.connect(self._clear_bind)
        bind_row.addWidget(self.bind_label, 1)
        bind_row.addWidget(self.bind_pick_btn)
        bind_row.addWidget(self.bind_file_btn)
        bind_row.addWidget(self.bind_clear_btn)
        form.addRow("绑定程序", bind_row)

        lang_row = QHBoxLayout()
        self.src_combo = QComboBox()
        self.dest_combo = QComboBox()
        for code, label in LANG_LABELS:
            self.src_combo.addItem(label, code)
            if code != "auto":
                self.dest_combo.addItem(label, code)
        lang_row.addWidget(self.src_combo)
        arrow = QLabel("→")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lang_row.addWidget(arrow)
        lang_row.addWidget(self.dest_combo)
        form.addRow("语言", lang_row)

        self.engine_combo = QComboBox()
        self.engine_combo.addItem("有道智云", "youdao")
        self.engine_combo.addItem("DeepL", "deepl")
        self.engine_combo.addItem("仅识别不翻译", "none")
        self.engine_combo.currentIndexChanged.connect(self._sync_key_fields)
        form.addRow("翻译引擎", self.engine_combo)
        for combo in (self.src_combo, self.dest_combo, self.engine_combo):
            _style_combo(combo)

        self.youdao_key_row, self.youdao_key = _secret_input("有道 App Key")
        self.youdao_secret_row, self.youdao_secret = _secret_input("有道 App Secret")
        self.deepl_key_row, self.deepl_key = _secret_input("DeepL API Key（免费版以 :fx 结尾）")
        form.addRow("有道 Key", self.youdao_key_row)
        form.addRow("有道 Secret", self.youdao_secret_row)
        form.addRow("DeepL Key", self.deepl_key_row)

        self.interval_slider, self.interval_value = _slider_row(30, 1500, 10)
        form.addRow("截图间隔", _wrap_slider(self.interval_slider, self.interval_value, "ms"))
        self.font_slider, self.font_value = _slider_row(14, 42, 1)
        form.addRow("字幕字号", _wrap_slider(self.font_slider, self.font_value, "px"))
        self.font_slider.valueChanged.connect(self.overlay.set_font_size)

        self.show_original = QCheckBox("同时显示原文")
        self.click_through = QCheckBox("字幕点击穿透（游戏时建议开启）")
        self.show_original.stateChanged.connect(
            lambda: self.overlay.set_show_original(self.show_original.isChecked())
        )
        self.click_through.stateChanged.connect(
            lambda: self.overlay.set_click_through(self.click_through.isChecked())
        )
        form.addRow("显示", self.show_original)
        form.addRow("交互", self.click_through)
        root.addWidget(card)

        buttons = QHBoxLayout()
        self.start_btn = QPushButton("开始翻译")
        self.stop_btn = QPushButton("暂停")
        self.stop_btn.setObjectName("Danger")
        self.stop_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.start)
        self.stop_btn.clicked.connect(self.stop)
        buttons.addWidget(self.start_btn, 1)
        buttons.addWidget(self.stop_btn)
        root.addLayout(buttons)

        hint = QLabel(
            "热键  Ctrl+Alt+R 框选  ·  Ctrl+Alt+S 开始/暂停  ·  Ctrl+Alt+H 显示/隐藏字幕\n"
            "拖动浅色边框可移动识别区，拉边角缩放。字幕条可单独拖动。\n"
            "绑定程序后识别框会跟随该窗口，并只截该窗口画面；不绑定则仍是屏幕固定区域。"
        )
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        root.addWidget(hint)

    def _load_fields(self) -> None:
        _select_data(self.src_combo, self._config.src_lang)
        _select_data(self.dest_combo, self._config.dest_lang)
        _select_data(self.engine_combo, self._config.engine)
        self.youdao_key.setText(self._config.youdao_app_key)
        self.youdao_secret.setText(self._config.youdao_app_secret)
        self.deepl_key.setText(self._config.deepl_api_key)
        self.interval_slider.setValue(self._config.interval_ms)
        self.font_slider.setValue(self._config.font_size)
        self.show_original.setChecked(self._config.show_original)
        self.click_through.setChecked(self._config.click_through)
        self._sync_key_fields()
        self._refresh_bind_label()

    def _collect_fields(self) -> None:
        self._config.src_lang = self.src_combo.currentData()
        self._config.dest_lang = self.dest_combo.currentData()
        self._config.engine = self.engine_combo.currentData()
        self._config.youdao_app_key = self.youdao_key.text().strip()
        self._config.youdao_app_secret = self.youdao_secret.text().strip()
        self._config.deepl_api_key = self.deepl_key.text().strip()
        self._config.interval_ms = self.interval_slider.value()
        self._config.font_size = self.font_slider.value()
        self._config.show_original = self.show_original.isChecked()
        self._config.click_through = self.click_through.isChecked()

    def _sync_key_fields(self) -> None:
        engine = self.engine_combo.currentData()
        youdao = engine == "youdao"
        deepl = engine == "deepl"
        self.youdao_key_row.setEnabled(youdao)
        self.youdao_secret_row.setEnabled(youdao)
        self.deepl_key_row.setEnabled(deepl)

    def _on_select_cancelled(self) -> None:
        self._restore_panel_after_select()
        if self._region.width() >= 8:
            self.frame.set_region(self._region)
            self.overlay.show()
        self._set_status("已取消框选")

    def _on_region_selected(self, rect: QRect) -> None:
        self._restore_panel_after_select()
        self._set_region(rect, apply_pipeline=False, snap_overlay=True)
        self.frame.set_region(rect)
        self.overlay.show()
        self._sync_bound_rel_from_region()
        self._set_status("已框选，可拖边框移动、拉边角缩放")

    def _on_region_resized(self, rect: QRect) -> None:
        self._set_region(rect, apply_pipeline=self._running, snap_overlay=False)
        if not self._applying_bind and not self.frame.is_dragging():
            self._sync_bound_rel_from_region()
        self._set_status(f"识别区域 {rect.width()}×{rect.height()}")

    def _set_region(self, rect: QRect, apply_pipeline: bool, snap_overlay: bool = False) -> None:
        self._region = QRect(rect)
        self.region_label.setText(f"{rect.width()}×{rect.height()}  @ ({rect.x()}, {rect.y()})")
        self.overlay.follow_region(rect, force=snap_overlay)
        if apply_pipeline:
            self._region_apply_timer.start(160)

    def _apply_region_to_pipeline(self) -> None:
        if self._running and self._region.width() >= 8:
            self._collect_fields()
            self.pipeline.configure(self._region, self._config, self._bound_hwnd)

    def _on_result(self, original: str, translated: str, is_error: bool) -> None:
        self.overlay.set_texts(original, translated, is_error)

    def _on_status(self, text: str) -> None:
        self._set_status(text)
        if text.startswith("启动失败"):
            QMessageBox.warning(self, "无法启动", text)

    def _on_pipeline_finished(self) -> None:
        self._running = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)


class _ComboStyle(QProxyStyle):
    def drawPrimitive(self, element, option, painter, widget=None) -> None:
        if element == QStyle.PrimitiveElement.PE_IndicatorArrowDown:
            return
        if widget is not None and widget.inherits("QComboBoxPrivateContainer"):
            if element in (
                QStyle.PrimitiveElement.PE_Frame,
                QStyle.PrimitiveElement.PE_Widget,
                QStyle.PrimitiveElement.PE_FrameWindow,
                QStyle.PrimitiveElement.PE_PanelMenu,
            ):
                return
        super().drawPrimitive(element, option, painter, widget)

    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QStyle.StyleHint.SH_ComboBox_PopupFrameStyle:
            return int(QFrame.Shape.NoFrame)
        return super().styleHint(hint, option, widget, returnData)


def _style_combo(combo: QComboBox) -> None:
    fusion = QStyleFactory.create("Fusion")
    combo.setStyle(_ComboStyle(fusion) if fusion is not None else _ComboStyle())
    view = QListView()
    view.setFrameShape(QFrame.Shape.NoFrame)
    view.setLineWidth(0)
    view.setSpacing(2)
    view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    combo.setView(view)
    combo.setMaxVisibleItems(10)
    combo.showPopup = lambda c=combo: _show_combo_popup(c)  # type: ignore[method-assign]


def _show_combo_popup(combo: QComboBox) -> None:
    view = combo.view()
    container = view.parentWidget() if view is not None else None
    if container is not None:
        container.setWindowFlags(
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        if isinstance(container, QFrame):
            container.setFrameShape(QFrame.Shape.NoFrame)
            container.setLineWidth(0)
            container.setMidLineWidth(0)
    QComboBox.showPopup(combo)


def _chevron_font_family() -> str:
    for name in ("Segoe Fluent Icons", "Segoe MDL2 Assets"):
        if QFontDatabase.hasFamily(name):
            return name
    return ""


def _chevron_png(color: str, filename: str) -> Path:
    folder = Path(__file__).resolve().parent / "assets"
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / filename
    dpr = 2
    logical = 12
    size = logical * dpr
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    family = _chevron_font_family()
    if family:
        font = QFont(family)
        font.setPixelSize(size)
        painter.setFont(font)
        painter.setPen(QColor(color))
        painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "\uE70D")
    else:
        scale = size / 12
        pen = QPen(QColor(color), 1.25 * scale)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPolyline(
            QPolygonF(
                [
                    QPointF(2.6 * scale, 4.35 * scale),
                    QPointF(6.0 * scale, 7.75 * scale),
                    QPointF(9.4 * scale, 4.35 * scale),
                ]
            )
        )
    painter.end()
    pix.save(str(dest), "PNG")
    return dest


def _qss_url(path: Path) -> str:
    return path.resolve().as_uri()


def _secret_input(placeholder: str) -> tuple[QWidget, QLineEdit]:
    box = QWidget()
    layout = QHBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    edit = QLineEdit()
    edit.setEchoMode(QLineEdit.EchoMode.Password)
    edit.setPlaceholderText(placeholder)
    toggle = QPushButton("显示")
    toggle.setObjectName("SecretToggle")
    toggle.setCheckable(True)
    toggle.setCursor(Qt.CursorShape.PointingHandCursor)
    toggle.setToolTip("显示或隐藏密钥")

    def on_toggled(checked: bool) -> None:
        edit.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )
        toggle.setText("隐藏" if checked else "显示")

    toggle.toggled.connect(on_toggled)
    layout.addWidget(edit, 1)
    layout.addWidget(toggle)
    return box, edit


def _slider_row(minimum: int, maximum: int, step: int) -> tuple[QSlider, QLabel]:
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setRange(minimum, maximum)
    slider.setSingleStep(step)
    slider.setPageStep(step)
    value = QLabel()
    value.setMinimumWidth(52)
    slider.valueChanged.connect(lambda v: value.setText(str(v)))
    value.setText(str(slider.value()))
    return slider, value


def _wrap_slider(slider: QSlider, value: QLabel, suffix: str) -> QWidget:
    box = QWidget()
    layout = QHBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(slider, 1)
    value.setText(f"{slider.value()}{suffix}")
    slider.valueChanged.connect(lambda v: value.setText(f"{v}{suffix}"))
    layout.addWidget(value)
    return box


def _has_keys(config: AppConfig) -> bool:
    if config.engine == "youdao":
        return bool(config.youdao_app_key and config.youdao_app_secret)
    if config.engine == "deepl":
        return bool(config.deepl_api_key)
    return True


def _select_data(combo: QComboBox, data: str) -> None:
    for i in range(combo.count()):
        if combo.itemData(i) == data:
            combo.setCurrentIndex(i)
            return
