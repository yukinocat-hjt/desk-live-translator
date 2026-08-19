from __future__ import annotations

import ctypes
import time
from threading import Lock

from PySide6.QtCore import QRect, QThread, Signal

from app.capture.change_detect import ChangeDetector
from app.capture.screen import ScreenCapturer, qrect_to_physical
from app.config import AppConfig
from app.ocr.engine import OcrEngine
from app.translate.base import create_translator
from app.translate.cache import TranslationCache


class Pipeline(QThread):
    result_ready = Signal(str, str, bool)
    status_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._running = False
        self._rect = QRect()
        self._config = AppConfig()
        self._generation = 0
        self._lock = Lock()

    def configure(self, rect: QRect, config: AppConfig) -> None:
        with self._lock:
            self._rect = QRect(rect)
            self._config = AppConfig.from_dict(config.to_dict())
            self._generation += 1

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        self._running = True
        with self._lock:
            cfg = AppConfig.from_dict(self._config.to_dict())

        try:
            ctypes.windll.ole32.CoInitialize(None)
        except Exception:
            pass

        capturer = ScreenCapturer()
        detector = ChangeDetector(cfg.change_threshold)
        ocr = OcrEngine(cfg.ocr_min_score, cfg.ocr_min_chars)
        cache = TranslationCache()
        pending = ""
        pending_since = 0.0
        already_sent = True
        last_gen = -1

        try:
            self.status_changed.emit("正在加载 OCR…")
            ocr.load()
            self.status_changed.emit(f"运行中（截图：{capturer.backend}）")
            while self._running:
                started = time.monotonic()
                with self._lock:
                    rect = QRect(self._rect)
                    cfg = AppConfig.from_dict(self._config.to_dict())
                    gen = self._generation
                if gen != last_gen:
                    detector.reset()
                    pending = ""
                    already_sent = True
                    last_gen = gen

                detector.threshold = cfg.change_threshold
                ocr.min_score = cfg.ocr_min_score
                ocr.min_chars = cfg.ocr_min_chars

                if rect.width() < 8 or rect.height() < 8:
                    self._idle(started, cfg.interval_ms)
                    continue

                x, y, w, h = qrect_to_physical(rect)
                frame = capturer.grab(x, y, w, h)
                now = time.monotonic()
                if frame is not None and detector.changed(frame):
                    text = ocr.recognize(frame).strip()
                    if text and text != pending:
                        pending = text
                        pending_since = now
                        already_sent = False

                ready = (
                    pending
                    and not already_sent
                    and (now - pending_since) * 1000 >= cfg.debounce_ms
                )
                if not ready:
                    self._idle(started, cfg.interval_ms)
                    continue

                translator = create_translator(cfg)
                key = TranslationCache.make_key(
                    pending, cfg.src_lang, cfg.dest_lang, translator.name
                )
                cached = cache.get(key)
                if cached is not None:
                    already_sent = True
                    self.result_ready.emit(pending, cached, False)
                    self.status_changed.emit("运行中")
                    self._idle(started, cfg.interval_ms)
                    continue

                self.status_changed.emit("翻译中…")
                try:
                    translated = translator.translate(pending, cfg.src_lang, cfg.dest_lang)
                    cache.put(key, translated)
                    if gen != self._generation:
                        continue
                    already_sent = True
                    self.result_ready.emit(pending, translated, False)
                    self.status_changed.emit("运行中")
                except Exception as exc:
                    already_sent = True
                    self.result_ready.emit(pending, str(exc), True)
                    self.status_changed.emit("翻译出错")
                self._idle(started, cfg.interval_ms)
        except Exception as exc:
            self.status_changed.emit(f"启动失败：{exc}")
        finally:
            capturer.close()
            self._running = False

    def _idle(self, started: float, interval_ms: int) -> None:
        remain_ms = interval_ms - int((time.monotonic() - started) * 1000)
        while self._running and remain_ms > 0:
            step = min(50, remain_ms)
            self.msleep(step)
            remain_ms -= step
