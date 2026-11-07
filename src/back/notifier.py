"""Slack 알림(hermes 봇). 점수 임계값 이상만, 하루 상한 내에서, 항목당 1회만 발송한다."""
import logging
import threading
import time

import httpx

from . import db
from .config import HTTP_RETRIES, HTTP_TIMEOUT, KST, USER_AGENT, env_int, env_str

log = logging.getLogger("airadar.notifier")
SLACK_URL = "https://slack.com/api/chat.postMessage"
_notify_lock = threading.Lock()  # 스케줄러·웹훅 백그라운드 작업이 동시에 발송하지 못하게 한다
FRESH_MINUTES = 30  # 오래된 백로그가 한꺼번에 발송되지 않도록 최근 항목만 대상


def send_slack(text: str) -> tuple[bool, str]:
    """chat.postMessage 를 호출한다. (성공 여부, 오류 메시지)를 반환한다. 토큰은 .env 에서만 읽는다."""
    token, channel = env_str("SLACK_BOT_TOKEN"), env_str("SLACK_CHANNEL_ID")
    if not token or not channel:
        return False, "SLACK_BOT_TOKEN/SLACK_CHANNEL_ID 가 설정되지 않았습니다"
    headers = {"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT}
    last = "알 수 없는 오류"
    for attempt in range(HTTP_RETRIES + 1):
        try:
            resp = httpx.post(SLACK_URL, headers=headers, timeout=HTTP_TIMEOUT,
                              json={"channel": channel, "text": text})
            resp.raise_for_status()
            body = resp.json()
            if body.get("ok"):
                return True, ""
            return False, f"Slack 오류: {body.get('error', 'unknown')}"  # 재시도 무의미
        except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError, ValueError) as exc:
            last = f"{type(exc).__name__}"
            if attempt < HTTP_RETRIES:
                time.sleep(2 ** attempt)
    return False, f"Slack 요청 실패: {last}"


def format_message(item: dict) -> str:
    """제목 + 링크 + 한글 요약 설명을 담아 전송한다."""
    label = {"kakaotalk": "카톡", "github": "GitHub", "hn": "HN"}.get(item["source"], item["source"])
    lines = [f"*[{label}] {item['title']}*  (점수 {item['score']}점)"]
    if item.get("url"):
        lines.append(item["url"])
    ko_desc = item.get("summary_ko") or item.get("summary")
    if ko_desc:
        lines.append(f"🇰🇷 *한글 요약:* {ko_desc[:200]}")
    return "\n".join(lines)


def sent_today(conn) -> int:
    """오늘(KST) 발송된 건수."""
    from datetime import datetime, timezone
    midnight = datetime.now(KST).replace(hour=0, minute=0, second=0, microsecond=0)
    start = midnight.astimezone(timezone.utc).isoformat(timespec="seconds")
    return conn.execute("SELECT COUNT(*) FROM items WHERE notified_at >= ?", (start,)).fetchone()[0]


def notify_pending() -> dict:
    """임계값 이상·미발송·최근 항목을 점수 높은 순으로 상한까지 발송한다."""
    if not _notify_lock.acquire(blocking=False):
        return {"sent": 0, "error": None, "skipped": "다른 알림 작업이 실행 중"}
    try:
        return _notify_locked()
    finally:
        _notify_lock.release()


def _notify_locked() -> dict:
    """락을 잡은 상태에서 실제 발송을 수행한다. 항목마다 즉시 커밋해 중복 발송을 막는다."""
    min_score = env_int("SLACK_MIN_SCORE", 10)
    daily_limit = env_int("SLACK_DAILY_LIMIT", 30)
    started, sent, error = db.now_iso(), 0, None
    with db.get_conn() as conn:
        remaining = daily_limit - sent_today(conn)
        rows = conn.execute(
            """SELECT * FROM items WHERE score >= ? AND notified_at IS NULL AND first_seen_at >= ?
               ORDER BY score DESC LIMIT ?""",
            (min_score, db.minutes_ago_iso(FRESH_MINUTES), max(remaining, 0)),
        ).fetchall()
        for row in rows:
            ok, err = send_slack(format_message(dict(row)))
            if not ok:
                error = err
                break
            conn.execute("UPDATE items SET notified_at=? WHERE id=?", (db.now_iso(), row["id"]))
            conn.commit()  # 발송 직후 기록: 중간에 실패해도 이미 보낸 글은 재발송되지 않는다
            sent += 1
    if rows:  # 발송 시도가 있었던 경우만 slack 로그를 남긴다
        db.record_run("slack", started, 0, len(rows), sent, "error" if error else "ok", error)
        if error:
            log.error("Slack 발송 실패: %s", error)
    return {"sent": sent, "error": error}
