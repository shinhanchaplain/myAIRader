"""API, 웹훅, 수집기 오류 처리, 알림 테스트."""
import httpx
import pytest
from fastapi.testclient import TestClient

from src.back import db, notifier
from src.back.collectors.base import BaseCollector, CollectError, http_get_json, run_collector
from src.back.main import app

TIP = "[꿀팁 공유] FastAPI에 APScheduler 60초 주기 수집기 붙일 때 max_instances=1 설정을 꼭 추가하세요"
HOOK = {"room": "AI 에이전트 트렌드방", "sender": "강개발", "message": TIP, "sent_at": "2026-11-07T08:58:00+09:00"}


@pytest.fixture
def client(temp_db):
    with TestClient(app) as c:
        yield c


def test_health_stats_items(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/stats").json()["total"] == 0
    assert client.get("/api/items").json() == []


def test_웹훅_저장_중복_잡담(client):
    r = client.post("/api/webhook/kakao", json=HOOK)
    assert r.json()["result"] == "stored"
    assert client.post("/api/webhook/kakao", json=HOOK).json()["result"] == "duplicate"
    chat = {**HOOK, "message": "ㅋㅋ 안녕하세요 반갑습니다"}
    assert client.post("/api/webhook/kakao", json=chat).json()["result"] == "rejected"
    items = client.get("/api/items?source=kakaotalk").json()
    assert len(items) == 1 and items[0]["room"] == HOOK["room"]
    assert any(x["source"] == "kakao_webhook" for x in client.get("/api/runs").json())


def test_웹훅_비밀헤더(client, monkeypatch):
    monkeypatch.setenv("KAKAO_WEBHOOK_SECRET", "s3cret")
    assert client.post("/api/webhook/kakao", json=HOOK).status_code == 401
    ok = client.post("/api/webhook/kakao", json=HOOK, headers={"X-Webhook-Secret": "s3cret"})
    assert ok.status_code == 200


def test_웹훅_허용방(client, monkeypatch):
    monkeypatch.setenv("KAKAO_ALLOWED_ROOMS", "특정방")
    assert client.post("/api/webhook/kakao", json={**HOOK, "room": "잡다방"}).status_code == 403
    assert client.post("/api/webhook/kakao", json=HOOK).status_code == 200  # 우선 키워드(AI) 방
    assert client.post("/api/webhook/kakao", json={**HOOK, "room": "특정방"}).status_code == 200


def test_웹훅_검증오류(client):
    assert client.post("/api/webhook/kakao", json={"room": "x"}).status_code == 422


def test_개인정보_마스킹_저장(client):
    msg = {**HOOK, "message": TIP + " 문의 010-1234-5678"}
    client.post("/api/webhook/kakao", json=msg)
    assert "010-1234" not in client.get("/api/items").json()[0]["summary"]


def test_수동_수집_알수없는_소스(client):
    assert client.post("/api/collect/run?source=nope").status_code == 404


class _Boom(BaseCollector):
    name = "boom"

    def collect(self):
        raise CollectError("실패")


def test_수집_실패는_로그에_error_기록(temp_db):
    assert run_collector(_Boom())["status"] == "error"
    assert db.query_runs()[0]["status"] == "error"


def test_타임아웃_재시도후_CollectError(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _s: None)
    calls = []

    def handler(request):
        calls.append(1)
        raise httpx.ConnectTimeout("t")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(CollectError):
        http_get_json("https://example.com/x", client=client)
    assert len(calls) == 3  # 최초 1 + 재시도 2


def test_슬랙_동시_실행에도_중복_발송_없음(temp_db, monkeypatch):
    import threading
    import time
    sent = []

    def slow_send(text):
        time.sleep(0.05)
        sent.append(text)
        return True, ""

    monkeypatch.setattr(notifier, "send_slack", slow_send)
    with db.get_conn() as conn:
        for i in range(5):
            db.insert_item(conn, {"source": "hn", "source_id": str(i), "title": f"t{i}", "score": 20})
    threads = [threading.Thread(target=notifier.notify_pending) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(sent) == 5  # 4개 작업이 동시에 돌아도 항목당 1회만 발송


def test_슬랙_임계값과_일일상한(temp_db, monkeypatch):
    sent = []
    monkeypatch.setattr(notifier, "send_slack", lambda text: (sent.append(text) or True, ""))
    monkeypatch.setenv("SLACK_DAILY_LIMIT", "2")
    with db.get_conn() as conn:
        for i, score in enumerate([9, 10, 11, 3]):
            db.insert_item(conn, {"source": "hn", "source_id": str(i), "title": f"t{i}", "score": score})
    assert notifier.notify_pending()["sent"] == 2     # 상한 2건, 점수 높은 순
    assert notifier.notify_pending()["sent"] == 0     # 재발송 없음
    assert "(점수 11" in sent[0]
