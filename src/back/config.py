"""환경 설정 헬퍼. 비밀값은 .env 에서만 읽는다."""
import os
from datetime import timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env", override=True)

KST = timezone(timedelta(hours=9))
USER_AGENT = "AIRadar/0.1 (education)"
HTTP_TIMEOUT = 10.0
HTTP_RETRIES = 2
PORT = 8020


def env_str(name: str, default: str = "") -> str:
    """환경 변수를 문자열로 읽는다(앞뒤 공백 제거)."""
    return os.environ.get(name, default).strip()


def env_int(name: str, default: int) -> int:
    """환경 변수를 정수로 읽는다. 잘못된 값이면 기본값을 쓴다."""
    try:
        return int(env_str(name, str(default)))
    except ValueError:
        return default


def env_list(name: str, default: str = "") -> list[str]:
    """쉼표로 구분된 환경 변수를 리스트로 읽는다."""
    return [v.strip() for v in env_str(name, default).split(",") if v.strip()]
