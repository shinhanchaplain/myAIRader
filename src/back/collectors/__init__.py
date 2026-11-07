"""수집기 레지스트리."""
from .base import BaseCollector
from .github import GitHubCollector
from .hn import HackerNewsCollector
from .kakaotalk import KakaoFileCollector


def get_collectors() -> dict[str, BaseCollector]:
    """이름 → 수집기 인스턴스 사전을 만든다."""
    items = [GitHubCollector(), HackerNewsCollector(), KakaoFileCollector()]
    return {c.name: c for c in items}
