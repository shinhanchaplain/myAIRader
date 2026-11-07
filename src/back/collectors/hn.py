"""Hacker News 신규글 수집기: newstories 중 아직 보지 못한 id 만 조회한다."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import httpx

from .. import db, scorer
from ..translator import translate_to_ko
from .base import BaseCollector, CollectError, http_get_json

BASE = "https://hacker-news.firebaseio.com/v0"
MAX_NEW_PER_RUN = 30
WORKERS = 5


class HackerNewsCollector(BaseCollector):
    """신규 글을 최대 30건씩 동시 5개로 조회해 저장한다."""

    name = "hn"

    def collect(self) -> dict:
        """newstories 에서 이미 저장된 id 를 제외하고 신규만 가져온다."""
        ids = http_get_json(f"{BASE}/newstories.json")
        if not isinstance(ids, list):
            raise CollectError("HN 목록 응답 형식이 올바르지 않습니다")
        with db.get_conn() as conn:
            seen = {r[0] for r in conn.execute("SELECT source_id FROM items WHERE source='hn'")}
            new_ids = [str(i) for i in ids if str(i) not in seen][:MAX_NEW_PER_RUN]
            with httpx.Client(timeout=10) as client, ThreadPoolExecutor(WORKERS) as pool:
                stories = list(pool.map(lambda i: self._fetch(client, i), new_ids))
            keywords = db.load_keywords(conn)
            inserted = 0
            for story in filter(None, stories):
                inserted += 1 if self._save(conn, story, keywords) else 0
        return {"fetched": len(new_ids), "inserted": inserted}

    @staticmethod
    def _fetch(client: httpx.Client, item_id: str) -> dict | None:
        """글 1건을 조회한다. 삭제/죽은 글은 None."""
        try:
            data = http_get_json(f"{BASE}/item/{item_id}.json", client=client)
        except CollectError:
            return None  # 개별 글 실패는 건너뛰고, 목록 실패만 전체 오류로 본다
        if not isinstance(data, dict) or data.get("deleted") or data.get("dead") or not data.get("title"):
            return None
        return data

    @staticmethod
    def _save(conn, story: dict, keywords: dict[str, float]) -> bool:
        """HN 글을 점수화해 저장한다."""
        published = datetime.fromtimestamp(story.get("time", 0), timezone.utc).isoformat(timespec="seconds")
        title = story["title"]
        text = (story.get("text") or "")[:300]
        points = int(story.get("score") or 0)
        comments = int(story.get("descendants") or 0)
        score, hits = scorer.score_item(title, text, points, published, keywords, hn_comments=comments)

        # 영문 제목/본문 한글 번역/요약
        source_text = text if text else title
        summary_ko = translate_to_ko(source_text)

        item = {
            "source": "hn", "source_id": str(story["id"]), "title": title,
            "url": story.get("url") or f"https://news.ycombinator.com/item?id={story['id']}",
            "summary": text, "summary_ko": summary_ko, "author": story.get("by"), "stars": 0,
            "published_at": published, "score": score, "tags": ",".join(hits),
        }
        return db.insert_item(conn, item) is not None
