"""REST API 와 카카오톡 웹훅."""
import hmac
import ipaddress
import logging
import sqlite3
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from . import db, notifier, scheduler
from .collectors.base import run_collector
from .collectors.kakaotalk import ingest_message, room_allowed
from .config import KST, env_int, env_str
from .report import generate_today_top5_report

log = logging.getLogger("airadar.routes")
router = APIRouter(prefix="/api")
MAX_BODY_BYTES = 8192


class KakaoWebhook(BaseModel):
    """알림 봇 표준 페이로드(4개 필드)."""
    room: str = Field(min_length=1, max_length=100)
    sender: str = Field(min_length=1, max_length=60)
    message: str = Field(min_length=1, max_length=4000)
    sent_at: datetime | None = None


@router.get("/health")
def health() -> dict:
    """서버·스케줄러 상태, 소스별 마지막 수집과 연속 실패 수."""
    sources: dict[str, dict] = {}
    with db.get_conn() as conn:
        for name in scheduler.COLLECTORS:
            runs = conn.execute(
                "SELECT status, started_at, error FROM collect_runs WHERE source=? ORDER BY id DESC LIMIT 10", (name,)
            ).fetchall()
            fails = 0
            for r in runs:
                if r["status"] == "ok":
                    break
                fails += 1
            last = runs[0] if runs else None
            sources[name] = {
                "last_status": last["status"] if last else None,
                "last_run_at": last["started_at"] if last else None,
                "last_error": last["error"] if last and last["status"] == "error" else None,
                "consecutive_failures": fails,
            }
    return {
        "status": "ok", "scheduler_running": scheduler.scheduler.running,
        "server_time": db.now_iso(), "next_run_at": scheduler.next_run_at(),
        "interval_seconds": scheduler.INTERVAL_SECONDS, "sources": sources,
    }


@router.get("/items")
def items(source: str | None = None, q: str | None = None, room: str | None = None,
          min_score: float = 0, limit: int = Query(50, ge=1, le=200)) -> list[dict]:
    """피드 조회."""
    return db.query_items(source, q, min_score, room, limit)


@router.get("/runs")
def runs(limit: int = Query(50, ge=1, le=200)) -> list[dict]:
    """수집 로그."""
    return db.query_runs(limit)


@router.get("/stats")
def stats() -> dict:
    """소스별 건수, 24시간 신규, 최근 1시간 수집 성공률, 오늘 Slack 발송 수."""
    with db.get_conn() as conn:
        by_source = {r["source"]: r["n"] for r in conn.execute("SELECT source, COUNT(*) n FROM items GROUP BY source")}
        new_24h = conn.execute("SELECT COUNT(*) FROM items WHERE first_seen_at >= ?", (db.minutes_ago_iso(1440),)).fetchone()[0]
        run_rows = conn.execute(
            "SELECT status, COUNT(*) n FROM collect_runs WHERE started_at >= ? AND source != 'slack' GROUP BY status",
            (db.minutes_ago_iso(60),),
        ).fetchall()
        total_runs = sum(r["n"] for r in run_rows)
        ok_runs = sum(r["n"] for r in run_rows if r["status"] == "ok")
        notified = notifier.sent_today(conn)
    return {
        "total": sum(by_source.values()), "by_source": by_source, "new_24h": new_24h,
        "success_rate": round(ok_runs / total_runs * 100, 1) if total_runs else None,
        "runs_last_hour": total_runs, "slack_sent_today": notified,
        "slack_daily_limit": env_int("SLACK_DAILY_LIMIT", 30),
    }


@router.post("/collect/run")
def collect_run(source: str = Query(...)) -> dict:
    """수동 수집(시연·디버깅). source = github | hn | kakao_file"""
    collector = scheduler.COLLECTORS.get(source)
    if collector is None:
        raise HTTPException(404, f"알 수 없는 소스입니다: {source}")
    return run_collector(collector)


@router.post("/notify/test")
def notify_test() -> dict:
    """Slack 테스트 메시지를 보낸다."""
    ok, err = notifier.send_slack("AI Radar 테스트 메시지입니다.")
    if not ok:
        raise HTTPException(502, err)
    return {"ok": True}


def _is_local_client(request: Request) -> bool:
    """클라이언트가 루프백/사설망(같은 Wi-Fi) 주소인지 확인한다."""
    host = request.client.host if request.client else ""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return host == "testclient"
    return ip.is_loopback or ip.is_private


def _check_auth(request: Request, secret_header: str | None) -> None:
    """비밀 헤더 검증. 비밀값이 비어 있으면 로컬/사설망 클라이언트만 허용한다."""
    secret = env_str("KAKAO_WEBHOOK_SECRET")
    if secret:
        if not secret_header or not hmac.compare_digest(secret_header, secret):
            raise HTTPException(401, "인증 실패")
    elif not _is_local_client(request):
        raise HTTPException(401, "인증 실패: KAKAO_WEBHOOK_SECRET 이 없으면 로컬 네트워크만 허용됩니다")


@router.post("/webhook/kakao")
def webhook_kakao(payload: KakaoWebhook, request: Request, background: BackgroundTasks,
                  x_webhook_secret: str | None = Header(default=None)) -> dict:
    """카톡 알림 봇이 쏘는 실시간 수신 엔드포인트. 잡담은 200 + rejected 로 응답한다."""
    _check_auth(request, x_webhook_secret)
    if int(request.headers.get("content-length") or 0) > MAX_BODY_BYTES:
        raise HTTPException(413, "요청 본문이 너무 큽니다")
    if not room_allowed(payload.room):
        raise HTTPException(403, "허용되지 않은 방")
    sent_at = payload.sent_at or datetime.now(KST)
    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=KST)
    started = db.now_iso()
    try:
        with db.get_conn() as conn:
            result = ingest_message(conn, payload.room, payload.sender, payload.message, sent_at)
    except (sqlite3.Error, ValueError, OSError) as exc:
        db.record_run("kakao_webhook", started, 0, 1, 0, "error", f"{type(exc).__name__}: {exc}"[:500])
        log.exception("웹훅 처리 실패")
        raise HTTPException(500, "내부 처리 오류") from exc
    db.record_run("kakao_webhook", started, 0, 1, int(result["result"] == "stored"), "ok")
    if result["result"] == "stored" and result["score"] >= env_int("SLACK_MIN_SCORE", 10):
        background.add_task(notifier.notify_pending)
    return result


@router.post("/reports/top5")
def export_top5_report() -> dict:
    """오늘 최고 점수 받은 글 5개씩(전체글 & 카카오톡) 정리하고 저장한다."""
    try:
        content, file_path, data = generate_today_top5_report()
        return {
            "ok": True,
            "file_path": file_path,
            "markdown": content,
            "top_overall": data["overall"],
            "top_kakao": data["kakao"],
        }
    except Exception as exc:
        log.exception("TOP 5 리포트 생성 실패")
        raise HTTPException(500, f"리포트 생성 실패: {exc}") from exc

