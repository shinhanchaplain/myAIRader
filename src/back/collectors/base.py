"""수집기 공통 베이스: HTTP 재시도 헬퍼와 실행 기록(run_collector)."""
import logging
import sqlite3
import time
from abc import ABC, abstractmethod

import httpx

from .. import db
from ..config import HTTP_RETRIES, HTTP_TIMEOUT, USER_AGENT

log = logging.getLogger("airadar.collector")


class CollectError(Exception):
    """수집 중 복구할 수 없는 오류(레이트리밋, 잘못된 응답 등)."""


class BaseCollector(ABC):
    """모든 수집기의 부모. collect() 는 {'fetched': int, 'inserted': int} 를 반환한다."""

    name: str = "base"

    @abstractmethod
    def collect(self) -> dict:
        """수집을 수행하고 {'fetched', 'inserted'} 요약을 반환한다."""


def http_get_json(url: str, params: dict | None = None, headers: dict | None = None,
                  client: httpx.Client | None = None) -> object:
    """타임아웃 10초, 재시도 2회(지수 백오프), 지정 User-Agent 로 JSON 을 가져온다."""
    merged = {"User-Agent": USER_AGENT, **(headers or {})}
    own = client is None
    client = client or httpx.Client(timeout=HTTP_TIMEOUT)
    last: Exception | None = None
    try:
        for attempt in range(HTTP_RETRIES + 1):
            try:
                resp = client.get(url, params=params, headers=merged)
                if resp.status_code in (403, 429) and resp.headers.get("x-ratelimit-remaining") == "0":
                    raise CollectError(f"레이트리밋 초과({resp.status_code}): {url}")
                if resp.status_code == 429:
                    raise CollectError(f"요청 한도 초과(429): {url}")
                resp.raise_for_status()
                return resp.json()
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                last = exc
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500:
                    break  # 4xx 는 재시도해도 소용없다
                if attempt < HTTP_RETRIES:
                    time.sleep(2 ** attempt)
            except ValueError as exc:  # 잘못된 JSON
                raise CollectError(f"잘못된 JSON 응답: {url}") from exc
    finally:
        if own:
            client.close()
    raise CollectError(f"요청 실패: {url} ({type(last).__name__}: {last})")


def run_collector(collector: BaseCollector) -> dict:
    """수집기를 실행하고 결과를 collect_runs 에 기록한다. 예외는 삼키지 않고 error 로 남긴다."""
    started = db.now_iso()
    t0 = time.monotonic()
    fetched = inserted = 0
    status, error = "ok", None
    try:
        result = collector.collect()
        fetched, inserted = result.get("fetched", 0), result.get("inserted", 0)
    except (CollectError, httpx.HTTPError, sqlite3.Error, OSError, ValueError) as exc:
        status, error = "error", f"{type(exc).__name__}: {exc}"[:500]
        log.error("수집 실패 [%s] %s", collector.name, error)
    duration = int((time.monotonic() - t0) * 1000)
    db.record_run(collector.name, started, duration, fetched, inserted, status, error)
    return {"source": collector.name, "status": status, "fetched": fetched,
            "inserted": inserted, "error": error, "duration_ms": duration}
