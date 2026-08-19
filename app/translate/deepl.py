from __future__ import annotations

import httpx

DEEPL_LANG = {
    "zh": "ZH",
    "en": "EN",
    "ja": "JA",
    "ko": "KO",
    "fr": "FR",
    "de": "DE",
    "es": "ES",
    "ru": "RU",
    "pt": "PT",
    "it": "IT",
}


class DeepLTranslator:
    name = "deepl"

    def __init__(self, api_key: str, timeout: float = 10.0) -> None:
        self.api_key = api_key.strip()
        self.timeout = timeout
        self.base_url = (
            "https://api-free.deepl.com/v2/translate"
            if self.api_key.endswith(":fx")
            else "https://api.deepl.com/v2/translate"
        )

    def translate(self, text: str, src: str, dest: str) -> str:
        headers = {
            "Authorization": f"DeepL-Auth-Key {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, str | list[str]] = {
            "text": [text],
            "target_lang": DEEPL_LANG.get(dest, dest.upper()),
        }
        if src and src != "auto":
            payload["source_lang"] = DEEPL_LANG.get(src, src.upper())
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(self.base_url, headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()
        translations = body.get("translations") or []
        if not translations:
            raise RuntimeError("DeepL 未返回译文")
        return str(translations[0].get("text") or "").strip() or text
