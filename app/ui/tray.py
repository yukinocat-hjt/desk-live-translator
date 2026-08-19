from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from app.ui.icons import make_app_icon


class TrayIcon(QSystemTrayIcon):
    def __init__(self, panel: QWidget) -> None:
        super().__init__(make_app_icon(), panel)
        self._panel = panel
        self.setToolTip("桌面实时翻译")
        menu = QMenu()
        show_action = QAction("打开控制面板", menu)
        show_action.triggered.connect(self._show_panel)
        quit_action = QAction("退出", menu)
        quit_action.triggered.connect(panel.request_quit)
        menu.addAction(show_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)

    def _show_panel(self) -> None:
        self._panel.show()
        self._panel.raise_()
        self._panel.activateWindow()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_panel()
