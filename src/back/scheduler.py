"""APScheduler 60초 무인 수집. 모든 작업은 max_instances=1, coalesce=True."""
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from .collectors import get_collectors
from .collectors.base import run_collector
from .notifier import notify_pending

INTERVAL_SECONDS = 60
scheduler = BackgroundScheduler(timezone="UTC")
COLLECTORS = get_collectors()


def start_scheduler() -> None:
    """수집 작업(github, hn, kakao_file)과 Slack 알림 작업을 등록하고 시작한다."""
    if scheduler.running:
        return
    first = datetime.now(timezone.utc) + timedelta(seconds=3)
    for name, collector in COLLECTORS.items():
        scheduler.add_job(
            run_collector, "interval", seconds=INTERVAL_SECONDS, args=[collector],
            id=name, next_run_time=first, max_instances=1, coalesce=True,
        )
    scheduler.add_job(
        notify_pending, "interval", seconds=INTERVAL_SECONDS, id="slack",
        next_run_time=first + timedelta(seconds=20), max_instances=1, coalesce=True,
    )
    scheduler.start()


def stop_scheduler() -> None:
    """스케줄러를 종료한다."""
    if scheduler.running:
        scheduler.shutdown(wait=False)


def next_run_at() -> str | None:
    """수집 작업 중 가장 빠른 다음 실행 시각(UTC ISO)."""
    times = [j.next_run_time for j in scheduler.get_jobs() if j.id in COLLECTORS and j.next_run_time]
    return min(times).isoformat(timespec="seconds") if times else None
