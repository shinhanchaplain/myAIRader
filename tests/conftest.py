"""공용 픽스처: 임시 DB, 스케줄러 비활성, 카톡/슬랙 환경 변수 초기화."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["RADAR_DISABLE_SCHEDULER"] = "1"


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """테스트마다 새 SQLite 파일을 쓰고 외부 설정을 비운다."""
    from src.back import db
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    for name in ("KAKAO_WEBHOOK_SECRET", "KAKAO_ALLOWED_ROOMS", "SLACK_BOT_TOKEN", "SLACK_CHANNEL_ID"):
        monkeypatch.delenv(name, raising=False)
    db.init_db()
    return db
