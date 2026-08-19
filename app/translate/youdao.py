from __future__ import annotations

import hashlib
import time
import uuid
from urllib.parse import urlencode

import httpx

YOUDAO_URL = "https://openapi.youdao.com/api"

YOUDAO_LANG = {
    "auto": "auto",
    "zh": "zh-CHS",
    "en": "en",
    "ja": "ja",
    "ko": "ko",
    "fr": "fr",
    "de": "de",
    "es": "es",
    "ru": "ru",
    "pt": "pt",
    "it": "it",
}

ERROR_HINTS = {
    "108": "应用ID无效，请检查有道 Key 是否粘贴完整。",
    "110": "账号没有开通文本翻译服务，请在有道智云绑定「文本翻译」。",
    "111": "开发者账号无效。",
    "202": "签名校验失败。请核对 Key/Secret，并重新复制（不要有空格）。若仍失败，多半是编码问题。",
    "203": "当前 IP 不在有道应用的白名单里。",
    "401": "有道账户欠费或免费额度用完。",
    "411": "访问频率受限，请把截图间隔调大。",
}


class YoudaoTranslator:
    name = "youdao"

    def __init__(self, app_key: str, app_secret: str, timeout: float = 10.0) -> None:
        self.app_key = _clean_secret(app_key)
        self.app_secret = _clean_secret(app_secret)
        self.timeout = timeout

    def translate(self, text: str, src: str, dest: str) -> str:
        q = _as_utf8(text)
        if not q:
            return ""
        salt = str(uuid.uuid1())
        curtime = str(int(time.time()))
        sign = _sign(self.app_key, q, salt, curtime, self.app_secret)
        form = {
            "q": q,
            "from": YOUDAO_LANG.get(src, src),
            "to": YOUDAO_LANG.get(dest, dest),
            "appKey": self.app_key,
            "salt": salt,
            "sign": sign,
            "signType": "v3",
            "curtime": curtime,
        }
        # 官方示例用 UTF-8 表单；必须带 charset，否则服务端按非 UTF-8 解码会返回 202
        body = urlencode(form, encoding="utf-8", errors="strict").encode("utf-8")
        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(YOUDAO_URL, content=body, headers=headers)
            response.raise_for_status()
            payload = response.json()
        code = str(payload.get("errorCode", "0"))
        if code != "0":
            hint = ERROR_HINTS.get(code, "")
            extra = f" {hint}" if hint else ""
            raise RuntimeError(f"有道翻译失败（errorCode={code}）。{extra}".strip())
        translation = payload.get("translation") or []
        return "\n".join(str(part) for part in translation).strip() or q


def _sign(app_key: str, text: str, salt: str, curtime: str, secret: str) -> str:
    raw = app_key + _truncate(text) + salt + curtime + secret
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _truncate(text: str) -> str:
    """Match Youdao's Java String.length() (UTF-16 code units), not Python len()."""
    units = _utf16_units(text)
    size = len(units)
    if size <= 20:
        return text
    return _from_utf16_units(units[:10]) + str(size) + _from_utf16_units(units[-10:])


def _utf16_units(text: str) -> list[bytes]:
    encoded = text.encode("utf-16-le")
    return [encoded[i : i + 2] for i in range(0, len(encoded), 2)]


def _from_utf16_units(units: list[bytes]) -> str:
    return b"".join(units).decode("utf-16-le")


def _as_utf8(text: str) -> str:
    return (text or "").encode("utf-8", errors="replace").decode("utf-8").strip()


def _clean_secret(value: str) -> str:
    cleaned = (value or "").strip().replace("\ufeff", "").replace("\u200b", "")
    return "".join(cleaned.split())
