"""다중 엔드포인트(Google dict-chrome-ex → MyMemory)와 메모리 캐시를 갖춘 한국어 번역 헬퍼.

외부 호출 규칙: 타임아웃 10초, 재시도 2회(지수 백오프), User-Agent 명시.
번역에 실패하면 빈 문자열을 반환하고 로그를 남긴다(원문을 한글 요약으로 위장하지 않는다).
"""
import logging
import re
import time
from typing import Callable

import httpx

from .config import HTTP_RETRIES, HTTP_TIMEOUT, USER_AGENT

log = logging.getLogger("airadar.translator")

GOOGLE_URL = "https://translate.googleapis.com/translate_a/single"
MYMEMORY_URL = "https://api.mymemory.translated.net/get"
MYMEMORY_MAX_LEN = 200  # MyMemory 무료 한도를 고려한 입력 길이 제한
HANGUL_RE = re.compile(r"[가-힣]")
_CACHE: dict[str, str] = {}
_CACHE_MAX = 2000


def is_mostly_korean(text: str) -> bool:
    """텍스트에 한글이 20% 이상 포함되어 있는지 확인한다."""
    if not text:
        return True
    return len(HANGUL_RE.findall(text)) / max(len(text.strip()), 1) > 0.2


def _get_json(url: str, params: dict) -> object:
    """GET 요청 후 JSON 을 반환한다. 일시 오류는 지수 백오프로 재시도한다."""
    last: httpx.HTTPError | None = None
    for attempt in range(HTTP_RETRIES + 1):
        try:
            resp = httpx.get(url, params=params, timeout=HTTP_TIMEOUT,
                             headers={"User-Agent": USER_AGENT})
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            last = exc
            if exc.response.status_code < 500:
                break  # 4xx(429 포함)는 재시도해도 소용없으니 다음 엔드포인트로 넘어간다
        except httpx.TransportError as exc:  # 타임아웃·연결 오류
            last = exc
        if attempt < HTTP_RETRIES:
            time.sleep(2 ** attempt)
    raise last if last else httpx.HTTPError("알 수 없는 오류")


def _translate_google(text: str) -> str:
    """Google Translate dict-chrome-ex 엔드포인트."""
    data = _get_json(GOOGLE_URL, {"client": "dict-chrome-ex", "sl": "auto", "tl": "ko", "dt": "t", "q": text})
    return "".join(p[0] for p in data[0] if p and p[0]).strip()  # type: ignore[index]


def _translate_mymemory(text: str) -> str:
    """MyMemory 무료 백업 엔드포인트."""
    data = _get_json(MYMEMORY_URL, {"q": text[:MYMEMORY_MAX_LEN], "langpair": "en|ko"})
    return str(data["responseData"]["translatedText"]).strip()  # type: ignore[index]


_ENGINES: list[tuple[str, Callable[[str], str]]] = [
    ("google", _translate_google),
    ("mymemory", _translate_mymemory),
]


def translate_to_ko(text: str, max_len: int = 300) -> str:
    """영문 텍스트를 한국어로 번역한다. 이미 한글이면 그대로, 모두 실패하면 빈 문자열을 반환한다."""
    if not text or not text.strip():
        return ""
    text = text.strip()[:max_len]
    if is_mostly_korean(text):
        return text
    if text in _CACHE:
        return _CACHE[text]

    for name, engine in _ENGINES:
        try:
            result = engine(text)
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
            log.warning("번역 실패 [%s] %s: %s", name, text[:30], exc)
            continue
        if result and is_mostly_korean(result):
            if len(_CACHE) >= _CACHE_MAX:
                _CACHE.clear()  # 단순 상한: 가득 차면 비운다
            _CACHE[text] = result
            return result
    return ""
