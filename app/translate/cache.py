from __future__ import annotations

from collections import OrderedDict
from threading import Lock


class TranslationCache:
    def __init__(self, maxsize: int = 256) -> None:
        self.maxsize = maxsize
        self._data: OrderedDict[str, str] = OrderedDict()
        self._lock = Lock()

    def get(self, key: str) -> str | None:
        with self._lock:
            value = self._data.get(key)
            if value is not None:
                self._data.move_to_end(key)
            return value

    def put(self, key: str, value: str) -> None:
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                self._data[key] = value
            else:
                self._data[key] = value
                if len(self._data) > self.maxsize:
                    self._data.popitem(last=False)

    @staticmethod
    def make_key(text: str, src: str, dest: str, engine: str) -> str:
        return f"{engine}|{src}|{dest}|{text}"
