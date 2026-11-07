"""다중 백업 엔드포인트와 메모리 캐시를 갖춘 고속 한국어 번역 헬퍼."""
import logging
import re
import httpx

log = logging.getLogger("airadar.translator")
HANGUL_RE = re.compile(r"[\uac00-\ud7a3]")
_CACHE: dict[str, str] = {}


def is_mostly_korean(text: str) -> bool:
    """텍스트에 한글이 20% 이상 포함되어 있는지 확인."""
    if not text:
        return True
    hangul_count = len(HANGUL_RE.findall(text))
    return (hangul_count / max(len(text.strip()), 1)) > 0.2


def _translate_chrome(text: str) -> str | None:
    """Google Translate Chrome Extension 엔드포인트 (429 차단 없음)."""
    resp = httpx.get(
        "https://translate.googleapis.com/translate_a/single",
        params={"client": "dict-chrome-ex", "sl": "auto", "tl": "ko", "dt": "t", "q": text},
        timeout=2.5,
    )
    if resp.status_code == 200:
        data = resp.json()
        pieces = [p[0] for p in data[0] if p and p[0]]
        res = "".join(pieces).strip()
        if res and is_mostly_korean(res):
            return res
    return None


def _translate_mymemory(text: str) -> str | None:
    """MyMemory 무료 백업 번역 엔드포인트."""
    resp = httpx.get(
        "https://api.mymemory.translated.net/get",
        params={"q": text[:200], "langpair": "en|ko"},
        timeout=2.5,
    )
    if resp.status_code == 200:
        res = resp.json().get("responseData", {}).get("translatedText", "").strip()
        if res and is_mostly_korean(res):
            return res
    return None


def translate_to_ko(text: str, max_len: int = 300) -> str:
    """영문 텍스트를 자연스러운 한국어로 번역/요약한다. 실패 시 빈 문자열 또는 원문 반환."""
    if not text or not text.strip():
        return ""
    text = text.strip()[:max_len]
    if is_mostly_korean(text):
        return text

    if text in _CACHE:
        return _CACHE[text]

    # 1차 시도: Google Chrome Ext 엔드포인트
    try:
        res = _translate_chrome(text)
        if res:
            _CACHE[text] = res
            return res
    except Exception:
        pass

    # 2차 시도: MyMemory 백업
    try:
        res = _translate_mymemory(text)
        if res:
            _CACHE[text] = res
            return res
    except Exception:
        pass

    return ""
