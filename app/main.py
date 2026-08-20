from __future__ import annotations

import os
import sys
from pathlib import Path

if __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from app.capture.dpi import enable_per_monitor_dpi

from app.config import AppConfig
from app.hotkeys import HotkeyManager
from app.ui.icons import make_app_icon
from app.ui.panel import ControlPanel
from app.ui.tray import TrayIcon


def _enable_dpi_awareness() -> None:
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")
    enable_per_monitor_dpi()


def main() -> int:
    _enable_dpi_awareness()
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("桌面实时翻译")
    app.setWindowIcon(make_app_icon())

    config = AppConfig.load()
    panel = ControlPanel(config)
    panel.show()

    tray = None
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = TrayIcon(panel)
        tray.show()
        tray.showMessage("桌面实时翻译", "已在托盘运行，关闭窗口会隐藏到托盘。", TrayIcon.MessageIcon.Information, 2500)

    hotkeys = HotkeyManager(config)
    try:
        hotkeys.start()
    except Exception as exc:
        panel._set_status(f"全局热键不可用：{exc}")

    hotkeys.select_region.connect(panel.start_region_select)
    hotkeys.toggle_run.connect(panel.toggle_run)
    hotkeys.toggle_overlay.connect(panel.toggle_overlay)

    app.aboutToQuit.connect(hotkeys.stop)
    code = app.exec()
    hotkeys.stop()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
