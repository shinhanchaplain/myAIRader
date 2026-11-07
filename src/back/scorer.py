"""규칙 기반 점수화(LLM 비용 0원, 설명 가능) + GitHub 반응 점수 고도화."""
import math
import re
from datetime import datetime, timezone

HALF_LIFE_HOURS = 12.0  # 반감기 12시간 (너무 빨리 점수가 깎이지 않도록 안정화)
URL_RE = re.compile(r"https?://", re.I)
NOTICE_RE = re.compile(r"공지|필독")


def _matches(text: str, word: str) -> int:
    """대소문자 무시 부분 일치 횟수(최대 3회까지만 인정)."""
    return min(text.lower().count(word.lower()), 3)


def decay_factor(published_at: str | None) -> float:
    """발행 후 경과 시간에 따른 감쇠(12시간 반감). 시각을 모르면 1.0."""
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


def github_reaction_bonus(stars: int, forks: int = 0) -> float:
    """GitHub 스타 및 포크 수에 따른 사용자 반응/인기도 점수."""
    score = 0.0
    if stars >= 5000:
        score += 9.0
    elif stars >= 2000:
        score += 7.5
    elif stars >= 1000:
        score += 6.0
    elif stars >= 500:
        score += 4.5
    elif stars >= 100:
        score += 3.0
    elif stars >= 50:
        score += 1.5

    # 연속적 스케일 가산 (스타 및 실제 사용하는 개발자 수인 포크 반영)
    score += math.log10(max(stars, 0) + 1) * 1.5
    if forks > 0:
        score += math.log10(max(forks, 0) + 1) * 1.0
    return round(score, 2)


def hn_reaction_bonus(points: int, comments: int = 0) -> float:
    """Hacker News 추천(points) 및 댓글(comments) 반응 점수."""
    score = 0.0
    if points >= 100:
        score += 6.0
    elif points >= 50:
        score += 4.0
    elif points >= 20:
        score += 2.5
    elif points >= 10:
        score += 1.5

    score += math.log10(max(points, 0) + 1) * 1.5
    if comments > 0:
        score += math.log10(max(comments, 0) + 1) * 1.2
    return round(score, 2)


def score_item(title: str, summary: str | None, stars: int, published_at: str | None,
               keywords: dict[str, float], bonus: float = 0.0, forks: int = 0,
               hn_comments: int = 0) -> tuple[float, list[str]]:
    """(점수, 매칭 키워드 목록)을 반환한다. 제목 가중 2배 + 반응(Star/Fork/Comment) 점수 + 시간 감쇠."""
    summary = summary or ""
    total = 0.0
    hits: list[str] = []
    for word, weight in keywords.items():
        t, s = _matches(title, word), _matches(summary, word)
        if t or s:
            hits.append(word)
            total += weight * (t * 2 + s)

    # 반응 점수 반영 (GitHub 스타/포크 or HN 점수/댓글)
    if hn_comments > 0:
        total += hn_reaction_bonus(stars, hn_comments)
    else:
        total += github_reaction_bonus(stars, forks)

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
