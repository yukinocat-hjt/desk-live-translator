from __future__ import annotations

from typing import Protocol

from app.config import AppConfig


class Translator(Protocol):
    name: str

    def translate(self, text: str, src: str, dest: str) -> str: ...


class PassthroughTranslator:
    name = "none"

    def translate(self, text: str, src: str, dest: str) -> str:
        return text


def create_translator(config: AppConfig) -> Translator:
    engine = (config.engine or "none").strip().lower()
    if engine == "youdao":
        from app.translate.youdao import YoudaoTranslator

        if config.youdao_app_key and config.youdao_app_secret:
            return YoudaoTranslator(config.youdao_app_key, config.youdao_app_secret)
    if engine == "deepl":
        from app.translate.deepl import DeepLTranslator

        if config.deepl_api_key:
            return DeepLTranslator(config.deepl_api_key)
    return PassthroughTranslator()


LANG_LABELS = [
    ("auto", "自动检测"),
    ("en", "英语"),
    ("zh", "简体中文"),
    ("ja", "日语"),
    ("ko", "韩语"),
    ("fr", "法语"),
    ("de", "德语"),
    ("es", "西班牙语"),
    ("ru", "俄语"),
    ("pt", "葡萄牙语"),
    ("it", "意大利语"),
]
