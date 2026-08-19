from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


APP_NAME = "DeskTranslate"


def config_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return config_dir() / "config.json"


@dataclass
class AppConfig:
    src_lang: str = "en"
    dest_lang: str = "zh"
    interval_ms: int = 400
    debounce_ms: int = 300
    font_size: int = 22
    engine: str = "youdao"
    show_original: bool = True
    click_through: bool = True
    ocr_min_score: float = 0.5
    ocr_min_chars: int = 2
    change_threshold: float = 8.0
    overlay_opacity: float = 0.78
    youdao_app_key: str = ""
    youdao_app_secret: str = ""
    deepl_api_key: str = ""
    select_hotkey: str = "<ctrl>+<alt>+r"
    toggle_run_hotkey: str = "<ctrl>+<alt>+s"
    toggle_overlay_hotkey: str = "<ctrl>+<alt>+h"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def save(self) -> None:
        path = config_path()
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls) -> "AppConfig":
        path = config_path()
        if not path.exists():
            cfg = cls()
            cfg.save()
            return cfg
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return cls()
            return cls.from_dict(data)
        except (OSError, json.JSONDecodeError):
            return cls()
