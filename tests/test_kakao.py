"""카톡 잡담 필터(골든 데이터)와 대화록 파서 테스트."""
from pathlib import Path

import pytest

from src.back import db
from src.back.collectors.kakao_filter import classify, mask_pii
from src.back.collectors.kakaotalk import KakaoFileCollector, parse_chat_text, to_24h

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "kakaotalk" / "sample_chat.txt"


@pytest.mark.parametrize("text,expected", [
    ("안녕하세요 여러분! 오늘 워크숍 다들 잘 오셨나요?", False),
    ("네 안녕하세요~ 반갑습니다! ㅎㅎ", False),
    ("ㅋㅋ 오늘 날씨 좋네요", False),
    ("와 대박이네요 링크 감사합니다!!", False),
    ("좋은 꿀팁 감사합니다 스크랩해둘게요!", False),
    ("ㅋㅋㅋㅋㅋㅋㅋㅋ", False),
    ("😀😀😀", False),
    ("", False),
    ("[필독 공지] Claude 신규 모델 https://www.anthropic.com/news/claude-3-7", True),
    ("[꿀팁 공유] FastAPI에 APScheduler 60초 주기 수집기 붙일 때 max_instances=1 설정을 꼭 추가하세요", True),
    ("논문 추천: Autonomous Multi-Agent Workflows https://arxiv.org/abs/2603.12345", True),
])
def test_필터_골든(text, expected):
    assert classify(text).passed is expected


def test_개인정보_마스킹():
    out = mask_pii("연락주세요 010-1234-5678 또는 test.user@example.com")
    assert "010-1234-5678" not in out and "example.com" not in out


def test_오전_오후_변환():
    assert to_24h("오전", 12) == 0 and to_24h("오후", 12) == 12 and to_24h("오후", 3) == 15


def test_샘플_파서_메시지_수():
    room, msgs = parse_chat_text(SAMPLE.read_text(encoding="utf-8"))
    assert room == "AI 실무 스킬 & 트렌드 오픈채팅방"
    assert len(msgs) == 8 and msgs[0]["sent_at"].hour == 8


def test_여러줄_메시지_이어붙임():
    text = "[방] 카카오톡 대화\n--------------- 2026년 11월 7일 토요일 ---------------\n[a] [오후 1:05] 첫줄\n둘째줄\n"
    _, msgs = parse_chat_text(text)
    assert msgs[0]["message"] == "첫줄\n둘째줄" and msgs[0]["sent_at"].hour == 13


def test_샘플_파일_수집_3건_재실행_중복없음(temp_db):
    collector = KakaoFileCollector(SAMPLE.parent)
    first = collector.collect()
    assert first["inserted"] == 3
    assert collector.collect() == {"fetched": 0, "inserted": 0}  # 변경 없는 파일은 건너뜀
    with db.get_conn() as conn:
        conn.execute("DELETE FROM file_cursors")
    assert collector.collect()["inserted"] == 0  # 커서가 없어도 UNIQUE 로 중복 0건
