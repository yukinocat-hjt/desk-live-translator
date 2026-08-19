from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from app.config import AppConfig


class HotkeyManager(QObject):
    select_region = Signal()
    toggle_run = Signal()
    toggle_overlay = Signal()

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config
        self._listener = None

    def start(self) -> None:
        from pynput.keyboard import GlobalHotKeys

        mapping = {
            self._config.select_hotkey: self.select_region.emit,
            self._config.toggle_run_hotkey: self.toggle_run.emit,
            self._config.toggle_overlay_hotkey: self.toggle_overlay.emit,
        }
        self._listener = GlobalHotKeys(mapping)
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
