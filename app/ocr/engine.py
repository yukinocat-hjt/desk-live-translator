from __future__ import annotations

import re
from typing import Any, Iterable

import numpy as np


class OcrEngine:
    """RapidOCR wrapper: filter by score/length and merge boxes into lines."""

    def __init__(self, min_score: float = 0.5, min_chars: int = 2) -> None:
        self.min_score = min_score
        self.min_chars = min_chars
        self._engine: Any = None

    def load(self) -> None:
        if self._engine is not None:
            return
        try:
            from rapidocr import RapidOCR
        except ImportError:
            from rapidocr_onnxruntime import RapidOCR  # type: ignore

        self._engine = RapidOCR()

    def recognize(self, image: np.ndarray) -> str:
        if self._engine is None:
            self.load()
        raw = self._engine(image)
        items = _normalize_result(raw)
        return merge_lines(items, self.min_score, self.min_chars)


def _normalize_result(raw: Any) -> list[tuple[Any, str, float]]:
    if raw is None:
        return []

    txts = getattr(raw, "txts", None)
    if txts is not None:
        boxes = getattr(raw, "boxes", None)
        scores = getattr(raw, "scores", None)
        items = []
        for i, text in enumerate(txts):
            if boxes is not None and i < len(boxes):
                box = boxes[i]
            else:
                box = [[0, 0], [0, 0], [0, 0], [0, 0]]
            if scores is not None and i < len(scores):
                score = float(scores[i])
            else:
                score = 1.0
            items.append((box, str(text), score))
        return items

    if isinstance(raw, tuple):
        raw = raw[0]
    if not raw:
        return []

    items = []
    for row in raw:
        if row is None or len(row) < 2:
            continue
        box, text = row[0], row[1]
        score = float(row[2]) if len(row) > 2 else 1.0
        items.append((box, str(text), score))
    return items


def merge_lines(
    items: Iterable[tuple[Any, str, float]],
    min_score: float,
    min_chars: int,
) -> str:
    filtered: list[tuple[float, float, float, str]] = []
    for box, text, score in items:
        cleaned = _clean_text(text)
        if score < min_score or len(cleaned) < min_chars:
            continue
        cy, cx, height = _box_metrics(box)
        filtered.append((cy, cx, height, cleaned))
    if not filtered:
        return ""

    filtered.sort(key=lambda item: item[0])
    lines: list[list[tuple[float, float, float, str]]] = [[filtered[0]]]
    for item in filtered[1:]:
        ref = lines[-1][-1]
        thresh = max(ref[2], item[2], 8.0) * 0.6
        if abs(item[0] - ref[0]) <= thresh:
            lines[-1].append(item)
        else:
            lines.append([item])

    merged = []
    for line in lines:
        line.sort(key=lambda item: item[1])
        merged.append(" ".join(part[3] for part in line))
    return "\n".join(merged)


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _box_metrics(box: Any) -> tuple[float, float, float]:
    points = np.asarray(box, dtype=np.float32).reshape(-1, 2)
    ys = points[:, 1]
    xs = points[:, 0]
    top, bottom = float(ys.min()), float(ys.max())
    return ((top + bottom) / 2.0, float(xs.min()), max(bottom - top, 1.0))
