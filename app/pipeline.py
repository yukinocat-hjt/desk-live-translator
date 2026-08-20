from __future__ import annotations

import ctypes
import time
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Lock

from PySide6.QtCore import QRect, QThread, Signal

from app.capture.change_detect import ChangeDetector
from app.capture.screen import ScreenCapturer, qrect_to_physical
from app.capture.window_grab import grab_window_region
from app.config import AppConfig
from app.ocr.engine import OcrEngine
from app.translate.base import create_translator
from app.translate.cache import TranslationCache

OCR_MIN_GAP_MS = 80
FORCE_OCR_MS = 800
FORCE_OCR_IDLE_MS = 2400
OCR_CONFIRM_SAME = 3
OCR_CONFIRM_EMPTY = 4


class Pipeline(QThread):
    result_ready = Signal(str, str, bool)
    status_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._running = False
        self._rect = QRect()
        self._config = AppConfig()
        self._hwnd = 0
        self._generation = 0
        self._lock = Lock()

    def configure(self, rect: QRect, config: AppConfig, hwnd: int = 0) -> None:
        with self._lock:
            self._rect = QRect(rect)
            self._config = AppConfig.from_dict(config.to_dict())
            self._hwnd = int(hwnd or 0)
            self._generation += 1

    def set_capture_hwnd(self, hwnd: int) -> None:
        with self._lock:
            self._hwnd = int(hwnd or 0)

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
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="dt-translate")
        pending = ""
        pending_since = 0.0
        already_sent = True
        last_gen = -1
        dirty = True
        empty_streak = 0
        same_streak = 0
        last_ocr_at = 0.0
        translate_future: Future[tuple[int, int, str, str, bool]] | None = None
        translate_token = 0

        def pump_translate() -> None:
            nonlocal translate_future, already_sent
            if translate_future is None or not translate_future.done():
                return
            try:
                token, job_gen, source, translated, is_error = translate_future.result()
            except Exception as exc:
                translate_future = None
                self.result_ready.emit(pending, str(exc), True)
                self.status_changed.emit("翻译出错")
                return
            translate_future = None
            if token != translate_token or source != pending:
                return
            if job_gen != self._generation:
                return
            already_sent = True
            self.result_ready.emit(source, translated, is_error)
            self.status_changed.emit("翻译出错" if is_error else "运行中")

        def submit_translate(text: str, job_cfg: AppConfig, job_gen: int) -> None:
            nonlocal translate_future, translate_token, already_sent
            translator = create_translator(job_cfg)
            key = TranslationCache.make_key(
                text, job_cfg.src_lang, job_cfg.dest_lang, translator.name
            )
            cached = cache.get(key)
            already_sent = True
            if cached is not None:
                self.result_ready.emit(text, cached, False)
                self.status_changed.emit("运行中")
                return
            translate_token += 1
            token = translate_token
            snap = AppConfig.from_dict(job_cfg.to_dict())
            self.status_changed.emit("翻译中…")
            translate_future = executor.submit(
                _run_translate, snap, text, token, job_gen, cache
            )

        try:
            self.status_changed.emit("正在加载 OCR…")
            ocr.load()
            capture_label = capturer.backend
            self.status_changed.emit(f"运行中（截图：{capture_label}）")
            while self._running:
                started = time.monotonic()
                pump_translate()
                with self._lock:
                    rect = QRect(self._rect)
                    cfg = AppConfig.from_dict(self._config.to_dict())
                    gen = self._generation
                    hwnd = self._hwnd
                if gen != last_gen:
                    detector.reset()
                    pending = ""
                    already_sent = True
                    dirty = True
                    empty_streak = 0
                    same_streak = 0
                    last_ocr_at = 0.0
                    translate_token += 1
                    last_gen = gen

                detector.threshold = cfg.change_threshold
                ocr.min_score = cfg.ocr_min_score
                ocr.min_chars = cfg.ocr_min_chars

                if rect.width() < 8 or rect.height() < 8:
                    self._idle(started, cfg.interval_ms, pump_translate)
                    continue

                frame = None
                used = capturer.backend
                if hwnd and len(cfg.bound_rel) == 4:
                    frame = grab_window_region(hwnd, cfg.bound_rel)
                    if frame is not None:
                        used = "window"
                if frame is None:
                    x, y, w, h = qrect_to_physical(rect)
                    frame = capturer.grab(x, y, w, h)
                if used != capture_label:
                    capture_label = used
                    self.status_changed.emit(f"运行中（截图：{capture_label}）")
                now = time.monotonic()
                if frame is not None and detector.changed(frame):
                    dirty = True
                    empty_streak = 0
                    same_streak = 0

                force_ms = FORCE_OCR_IDLE_MS if empty_streak >= OCR_CONFIRM_EMPTY else FORCE_OCR_MS
                ocr_gap_ms = (now - last_ocr_at) * 1000 if last_ocr_at else force_ms
                should_ocr = (
                    frame is not None
                    and (dirty or ocr_gap_ms >= force_ms)
                    and ocr_gap_ms >= OCR_MIN_GAP_MS
                )
                if should_ocr:
                    text = ocr.recognize(frame).strip()
                    last_ocr_at = now
                    if not text:
                        empty_streak += 1
                        same_streak = 0
                        if empty_streak >= OCR_CONFIRM_EMPTY:
                            dirty = False
                    elif text == pending:
                        same_streak += 1
                        empty_streak = 0
                        if same_streak >= OCR_CONFIRM_SAME:
                            dirty = False
                    else:
                        pending = text
                        pending_since = now
                        already_sent = False
                        dirty = False
                        empty_streak = 0
                        same_streak = 0

                ready = (
                    pending
                    and not already_sent
                    and (now - pending_since) * 1000 >= cfg.debounce_ms
                )
                if ready:
                    submit_translate(pending, cfg, gen)
                self._idle(started, cfg.interval_ms, pump_translate)
        except Exception as exec_err:
            self.status_changed.emit(f"启动失败：{exec_err}")
        finally:
            capturer.close()
            executor.shutdown(wait=False, cancel_futures=True)
            self._running = False

    def _idle(self, started: float, interval_ms: int, pump=None) -> None:
        remain_ms = interval_ms - int((time.monotonic() - started) * 1000)
        while self._running and remain_ms > 0:
            step = min(50, remain_ms)
            self.msleep(step)
            remain_ms -= step
            if pump is not None:
                pump()


def _run_translate(
    config: AppConfig,
    text: str,
    token: int,
    generation: int,
    cache: TranslationCache,
) -> tuple[int, int, str, str, bool]:
    translator = create_translator(config)
    key = TranslationCache.make_key(text, config.src_lang, config.dest_lang, translator.name)
    try:
        translated = translator.translate(text, config.src_lang, config.dest_lang)
        cache.put(key, translated)
        return token, generation, text, translated, False
    except Exception as exc:
        return token, generation, text, str(exc), True
