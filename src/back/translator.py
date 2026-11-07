"""Google Translate 비공식 엔드포인트를 활용한 가벼운 한국어 번역 헬퍼."""
import logging
import re
import time
import httpx

log = logging.getLogger("airadar.translator")
TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"
HANGUL_RE = re.compile(r"[\uac00-\ud7a3]")


def is_mostly_korean(text: str) -> bool:
    """텍스트에 한글이 20% 이상 포함되어 있는지 확인."""
    if not text:
        return True
    hangul_count = len(HANGUL_RE.findall(text))
    return (hangul_count / len(text.strip())) > 0.2


def translate_to_ko(text: str, max_len: int = 500) -> str:
    """영문 텍스트를 자연스러운 한국어로 번역/요약한다. 실패 시 원문 반환."""
    if not text or not text.strip():
        return ""
    text = text.strip()[:max_len]
    if is_mostly_korean(text):
        return text

    params = {"client": "gtx", "sl": "auto", "tl": "ko", "dt": "t", "q": text}
    for attempt in range(3):  # 최초 1회 + 재시도 2회(지수 백오프)
        try:
            resp = httpx.get(TRANSLATE_URL, params=params, timeout=10.0,
                             headers={"User-Agent": "AIRadar/0.1 (education)"})
            resp.raise_for_status()
            # data[0]에 번역된 문장 조각들이 배열로 들어옴
            pieces = [p[0] for p in resp.json()[0] if p and p[0]]
            return "".join(pieces).strip() or text
        except (httpx.HTTPError, ValueError, IndexError, TypeError) as exc:
            log.warning("한글 번역 실패 %d/3 (%s): %s", attempt + 1, text[:30], exc)
            if attempt < 2:
                time.sleep(2 ** attempt)

    return text
