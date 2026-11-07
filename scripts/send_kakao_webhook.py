"""웹훅 테스트 스크립트: 카톡 알림 봇 대신 샘플 글을 POST 한다.

사용법: python scripts/send_kakao_webhook.py [서버주소] [방 이름] [메시지]
예)    python scripts/send_kakao_webhook.py http://192.168.0.10:8020
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import httpx
from dotenv import load_dotenv

load_dotenv()
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8020"
ROOM = sys.argv[2] if len(sys.argv) > 2 else "AI 실무 스킬 & 트렌드 오픈채팅방"
SAMPLES = [
    "안녕하세요 ㅎㅎ 반갑습니다",
    "[필독 공지] 새 Claude 에이전트 가이드가 공개되었습니다 https://docs.anthropic.com/",
    "[꿀팁 공유] 프롬프트에 역할과 제약조건을 먼저 적으면 에이전트 결과가 훨씬 안정적입니다.",
]

if __name__ == "__main__":
    headers = {}
    if os.environ.get("KAKAO_WEBHOOK_SECRET"):
        headers["X-Webhook-Secret"] = os.environ["KAKAO_WEBHOOK_SECRET"]
    kst = timezone(timedelta(hours=9))
    msgs = [sys.argv[3]] if len(sys.argv) > 3 else SAMPLES
    for text in msgs:
        body = {"room": ROOM, "sender": "테스트봇", "message": text, "sent_at": datetime.now(kst).isoformat()}
        resp = httpx.post(f"{BASE}/api/webhook/kakao", json=body, headers=headers, timeout=10)
        print(resp.status_code, resp.text)
