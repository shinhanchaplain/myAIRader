"""GitHub Search API 수집기: 토픽별 stars>50, 최근 갱신순."""
from .. import db, scorer
from ..config import env_str
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
        fetched = inserted = 0
        with db.get_conn() as conn:
            keywords = db.load_keywords(conn)
            for topic in topics:
                data = http_get_json(
                    SEARCH_URL,
                    params={"q": f"topic:{topic} stars:>50", "sort": "updated", "order": "desc", "per_page": 20},
                    headers=headers,
                )
                if not isinstance(data, dict) or "items" not in data:
                    raise CollectError("GitHub 응답 형식이 올바르지 않습니다")
                for repo in data["items"]:
                    fetched += 1
                    inserted += self._save(conn, repo, keywords)
        return {"fetched": fetched, "inserted": inserted}

    @staticmethod
    def _save(conn, repo: dict, keywords: dict[str, float]) -> int:
        """레포 1건을 저장한다. 신규면 1, 중복이면 0."""
        title = repo.get("full_name") or ""
        if not title:
            return 0
        summary = (repo.get("description") or "")[:300]
        stars = int(repo.get("stargazers_count") or 0)
        pushed = repo.get("pushed_at")
        score, hits = scorer.score_item(title, summary, stars, pushed, keywords)
        item = {
            "source": "github", "source_id": title, "title": title,
            "url": repo.get("html_url"), "summary": summary,
            "author": (repo.get("owner") or {}).get("login"), "stars": stars,
            "published_at": pushed, "score": score, "tags": ",".join(hits),
        }
        return 1 if db.insert_item(conn, item) else 0
