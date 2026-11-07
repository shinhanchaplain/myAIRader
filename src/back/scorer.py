"""규칙 기반 점수화(LLM 비용 0원, 설명 가능)."""
import math
import re
from datetime import datetime, timezone

HALF_LIFE_HOURS = 6.0
URL_RE = re.compile(r"https?://", re.I)
NOTICE_RE = re.compile(r"공지|필독")


def _matches(text: str, word: str) -> int:
    """대소문자 무시 부분 일치 횟수(최대 3회까지만 인정)."""
    return min(text.lower().count(word.lower()), 3)


def decay_factor(published_at: str | None) -> float:
    """발행 후 경과 시간에 따른 감쇠(6시간 반감). 시각을 모르면 1.0."""
    if not published_at:
        return 1.0
    try:
        dt = datetime.fromisoformat(published_at)
    except ValueError:
        return 1.0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    hours = max((datetime.now(timezone.utc) - dt).total_seconds() / 3600, 0)
    return 0.5 ** (hours / HALF_LIFE_HOURS)


def score_item(title: str, summary: str | None, stars: int, published_at: str | None,
               keywords: dict[str, float], bonus: float = 0.0) -> tuple[float, list[str]]:
    """(점수, 매칭 키워드 목록)을 반환한다. 제목 가중 2배, 별 개수는 로그 스케일."""
    summary = summary or ""
    total = 0.0
    hits: list[str] = []
    for word, weight in keywords.items():
        t, s = _matches(title, word), _matches(summary, word)
        if t or s:
            hits.append(word)
            total += weight * (t * 2 + s)
    total += math.log10(max(stars, 0) + 1) * 0.5
    total = (total + bonus) * decay_factor(published_at)
    return round(total, 2), hits


def kakao_bonus(text: str, priority_room: bool) -> float:
    """카톡 글 가산점: 공지/필독 +3, URL +2, 100자 이상 +1, 우선 방 +1."""
    bonus = 0.0
    if NOTICE_RE.search(text):
        bonus += 3
    if URL_RE.search(text):
        bonus += 2
    if len(text) >= 100:
        bonus += 1
    if priority_room:
        bonus += 1
    return bonus
