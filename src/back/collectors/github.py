"""GitHub Search API 수집기: 토픽별 stars>50, 최근 갱신순."""
from .. import db, scorer
from ..config import env_str
from ..translator import translate_to_ko
from .base import BaseCollector, CollectError, http_get_json

SEARCH_URL = "https://api.github.com/search/repositories"
TOPICS = ["ai-agent", "mcp", "claude-code", "llm"]
TOPICS_WITHOUT_TOKEN = TOPICS[:2]  # 무인증은 분당 10회 한도라 토픽을 줄인다


class GitHubCollector(BaseCollector):
    """토픽별 검색 결과를 items 에 저장한다."""

    name = "github"

    def collect(self) -> dict:
        """토큰이 있으면 토픽 4개, 없으면 2개를 조회한다."""
        token = env_str("GITHUB_TOKEN")
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        topics = TOPICS if token else TOPICS_WITHOUT_TOKEN
        # 1단계: 네트워크 조회 (DB 연결 없음)
        repos: list[dict] = []
        for topic in topics:
            data = http_get_json(
                SEARCH_URL,
                params={"q": f"topic:{topic} stars:>50", "sort": "updated", "order": "desc", "per_page": 20},
                headers=headers,
            )
            if not isinstance(data, dict) or "items" not in data:
                raise CollectError("GitHub 응답 형식이 올바르지 않습니다")
            repos.extend(data["items"])

        # 2단계: 짧은 읽기 후 점수화 + 신규 글만 번역 (DB 연결 없음 → 락 점유 없음)
        with db.get_conn() as conn:
            keywords = db.load_keywords(conn)
            seen = {r[0] for r in conn.execute("SELECT source_id FROM items WHERE source='github'")}
        items = [it for it in (self._build(r, keywords, seen) for r in repos) if it]

        # 3단계: 쓰기 트랜잭션은 저장만 짧게 수행
        inserted = 0
        with db.get_conn() as conn:
            for item in items:
                inserted += 1 if db.insert_item(conn, item) else 0
        return {"fetched": len(repos), "inserted": inserted}

    @staticmethod
    def _build(repo: dict, keywords: dict[str, float], seen: set[str]) -> dict | None:
        """레포 1건을 점수화한 항목 dict 로 만든다. 이미 저장된 글은 번역을 생략한다."""
        title = repo.get("full_name") or ""
        if not title:
            return None
        summary = (repo.get("description") or "")[:300]
        stars = int(repo.get("stargazers_count") or 0)
        forks = int(repo.get("forks_count") or 0)
        pushed = repo.get("pushed_at")
        score, hits = scorer.score_item(title, summary, stars, pushed, keywords, forks=forks)

        # 신규 글만 한글 요약 생성 (번역 실패 시 빈 값 → 원문 중복 표시 방지)
        summary_ko = "" if title in seen else translate_to_ko(summary or title)
        return {
            "source": "github", "source_id": title, "title": title,
            "url": repo.get("html_url"), "summary": summary, "summary_ko": summary_ko,
            "author": (repo.get("owner") or {}).get("login"), "stars": stars,
            "published_at": pushed, "score": score, "tags": ",".join(hits),
        }
