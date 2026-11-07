"""SQLite 저장소. items 는 UNIQUE(source, source_id)로 중복을 원천 차단한다."""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator

from .config import ROOT_DIR

DB_PATH = os.environ.get("RADAR_DB_PATH") or str(ROOT_DIR / "data" / "radar.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  source        TEXT NOT NULL,
  source_id     TEXT NOT NULL,
  title         TEXT NOT NULL,
  url           TEXT,
  summary       TEXT,
  author        TEXT,
  stars         INTEGER DEFAULT 0,
  published_at  TEXT,
  first_seen_at TEXT NOT NULL,
  last_seen_at  TEXT NOT NULL,
  score         REAL DEFAULT 0,
  tags          TEXT DEFAULT '',
  room          TEXT,
  notified_at   TEXT,
  filter_tags   TEXT DEFAULT '',
  summary_ko    TEXT,
  UNIQUE(source, source_id)
);
CREATE TABLE IF NOT EXISTS collect_runs (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  source      TEXT NOT NULL,
  started_at  TEXT NOT NULL,
  duration_ms INTEGER,
  fetched     INTEGER DEFAULT 0,
  inserted    INTEGER DEFAULT 0,
  status      TEXT NOT NULL,
  error       TEXT
);
CREATE TABLE IF NOT EXISTS keywords (
  word   TEXT PRIMARY KEY,
  weight REAL DEFAULT 1.0
);
CREATE TABLE IF NOT EXISTS file_cursors (
  path       TEXT PRIMARY KEY,
  size_bytes INTEGER NOT NULL,
  mtime      REAL NOT NULL,
  parsed_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_items_score ON items(score DESC, first_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_items_notify ON items(notified_at, score);
CREATE INDEX IF NOT EXISTS idx_runs_started ON collect_runs(started_at DESC);
"""

DEFAULT_KEYWORDS = {
    "agent": 2.0, "에이전트": 2.0, "claude": 2.0, "클로드": 2.0, "mcp": 2.0,
    "claude code": 3.0, "codex": 1.5, "gpt": 1.5, "llm": 1.0, "rag": 1.0,
    "vibe coding": 2.0, "바이브 코딩": 2.0, "프롬프트": 1.5, "꿀팁": 1.5,
    "공지": 1.0, "필독": 1.0, "논문": 1.0, "스킬": 1.0, "교육": 1.0,
    "education": 1.0, "자동화": 1.0,
}


def now_iso() -> str:
    """현재 시각을 UTC ISO8601 문자열로 반환한다."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def minutes_ago_iso(minutes: int) -> str:
    """minutes 분 전 시각을 UTC ISO8601 문자열로 반환한다."""
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat(timespec="seconds")


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    """커밋/롤백/종료를 보장하는 연결 컨텍스트. 호출 시점의 DB_PATH 를 사용한다."""
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        yield conn
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """테이블을 만들고 기본 키워드를 시드한다(여러 번 호출해도 안전)."""
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        conn.executemany(
            "INSERT OR IGNORE INTO keywords(word, weight) VALUES (?, ?)",
            list(DEFAULT_KEYWORDS.items()),
        )


def load_keywords(conn: sqlite3.Connection) -> dict[str, float]:
    """키워드 가중치 사전을 반환한다."""
    return {r["word"]: r["weight"] for r in conn.execute("SELECT word, weight FROM keywords")}


def insert_item(conn: sqlite3.Connection, item: dict) -> int | None:
    """항목을 INSERT OR IGNORE 로 저장한다. 신규면 id, 중복이면 None 을 반환한다."""
    now = now_iso()
    cur = conn.execute(
        """INSERT OR IGNORE INTO items
           (source, source_id, title, url, summary, summary_ko, author, stars, published_at,
            first_seen_at, last_seen_at, score, tags, room, filter_tags)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            item["source"], item["source_id"], item["title"], item.get("url"),
            item.get("summary"), item.get("summary_ko"), item.get("author"), item.get("stars", 0),
            item.get("published_at"), now, now, item.get("score", 0.0),
            item.get("tags", ""), item.get("room"), item.get("filter_tags", ""),
        ),
    )
    if cur.rowcount == 1:
        return cur.lastrowid
    conn.execute(
        "UPDATE items SET last_seen_at=?, stars=MAX(stars, ?), score=MAX(score, ?) WHERE source=? AND source_id=?",
        (now, item.get("stars", 0), item.get("score", 0.0), item["source"], item["source_id"]),
    )
    return None


def record_run(source: str, started_at: str, duration_ms: int, fetched: int,
               inserted: int, status: str, error: str | None = None) -> None:
    """수집 실행 결과를 collect_runs 에 남긴다(신규 0건이어도 ok 하트비트)."""
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO collect_runs(source, started_at, duration_ms, fetched, inserted, status, error)
               VALUES (?,?,?,?,?,?,?)""",
            (source, started_at, duration_ms, fetched, inserted, status, error),
        )
        # 7일 지난 로그는 정리한다
        conn.execute("DELETE FROM collect_runs WHERE started_at < ?", (minutes_ago_iso(7 * 24 * 60),))


def query_items(source: str | None = None, q: str | None = None, min_score: float = 0,
                room: str | None = None, limit: int = 50) -> list[dict]:
    """피드 조회. 모든 조건은 파라미터 바인딩을 사용한다."""
    sql = "SELECT * FROM items WHERE score >= ?"
    args: list = [min_score]
    if source:
        sql += " AND source = ?"
        args.append(source)
    if room:
        sql += " AND room = ?"
        args.append(room)
    if q:
        sql += " AND (title LIKE ? OR summary LIKE ?)"
        args += [f"%{q}%", f"%{q}%"]
    sql += " ORDER BY first_seen_at DESC, score DESC LIMIT ?"
    args.append(max(1, min(limit, 200)))
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql, args)]


def query_runs(limit: int = 50) -> list[dict]:
    """최근 수집 로그를 반환한다."""
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM collect_runs ORDER BY id DESC LIMIT ?", (max(1, min(limit, 200)),))
        return [dict(r) for r in rows]
