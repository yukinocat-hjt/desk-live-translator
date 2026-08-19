from __future__ import annotations

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.capture.region import RegionSelector
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
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #f5b84c;
}
QLineEdit:disabled, QComboBox:disabled {
    background: #f0f2f5;
    color: #9aa1ad;
}
QComboBox QAbstractItemView {
    background: #ffffff;
    color: #1c212b;
    selection-background-color: #fff3d6;
    selection-color: #1c212b;
    border: 1px solid #e4e7ec;
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
        self.setStyleSheet(STYLESHEET)
        self.setMinimumWidth(430)
        self._config = config
        self._region = QRect()
        self._quitting = False
        self._running = False

        self.overlay = OverlayWindow()
        self.frame = RegionFrame()
        self.selector = RegionSelector()
        self.pipeline = Pipeline()
        self._region_apply_timer = QTimer(self)
        self._region_apply_timer.setSingleShot(True)
        self._region_apply_timer.timeout.connect(self._apply_region_to_pipeline)
        self.pipeline.result_ready.connect(self._on_result)
        self.pipeline.status_changed.connect(self._on_status)
        self.pipeline.finished.connect(self._on_pipeline_finished)
        self.selector.selected.connect(self._on_region_selected)
        self.selector.cancelled.connect(self._on_select_cancelled)
        self.frame.region_changed.connect(self._on_region_resized)

        self._build_ui()
        self._load_fields()
        self.overlay.set_font_size(self._config.font_size)
        self.overlay.set_show_original(self._config.show_original)
        self.overlay.set_opacity(self._config.overlay_opacity)
        self.overlay.set_click_through(self._config.click_through)

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
        self.overlay.hide()
        self.frame.hide()
        QTimer.singleShot(120, self.selector.start)
        self._set_status("拖拽框选翻译区域")

    def start(self) -> None:
        self._collect_fields()
        if self._region.width() < 8:
            self.start_region_select()
            return
        self._config.save()
        if self.pipeline.isRunning():
            self.pipeline.stop()
            self.pipeline.wait(2000)
        self.pipeline.configure(self._region, self._config)
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
        self._config.save()
        from PySide6.QtWidgets import QApplication

        QApplication.instance().quit()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._quitting:
            event.accept()
            return
        event.ignore()
        self.hide()

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

        self.youdao_key_row, self.youdao_key = _secret_input("有道 App Key")
        self.youdao_secret_row, self.youdao_secret = _secret_input("有道 App Secret")
        self.deepl_key_row, self.deepl_key = _secret_input("DeepL API Key（免费版以 :fx 结尾）")
        form.addRow("有道 Key", self.youdao_key_row)
        form.addRow("有道 Secret", self.youdao_secret_row)
        form.addRow("DeepL Key", self.deepl_key_row)

        self.interval_slider, self.interval_value = _slider_row(100, 1500, 50)
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
            "拖动浅色边框可移动识别区，拉边角缩放。字幕条可单独拖动。"
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
        if self._region.width() >= 8:
            self.frame.set_region(self._region)
            self.overlay.show()
        self._set_status("已取消框选")

    def _on_region_selected(self, rect: QRect) -> None:
        self._set_region(rect, apply_pipeline=False, snap_overlay=True)
        self.frame.set_region(rect)
        self.overlay.show()
        self._set_status("已框选，可拖边框移动、拉边角缩放")

    def _on_region_resized(self, rect: QRect) -> None:
        self._set_region(rect, apply_pipeline=self._running, snap_overlay=False)
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
            self.pipeline.configure(self._region, self._config)

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
