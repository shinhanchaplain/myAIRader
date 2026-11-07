"""카카오톡 수집: 대화록(.txt) 파서와 웹훅 공용 저장 로직(ingest_message)."""
import hashlib
import logging
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .. import db, scorer
from ..config import KST, ROOT_DIR, env_list
from .base import BaseCollector
from .kakao_filter import URL_RE, classify, mask_pii

log = logging.getLogger("airadar.kakao")

CHAT_DIR = ROOT_DIR / "data" / "kakaotalk"
DEFAULT_PRIORITY_ROOM_WORDS = "AI,에이전트,스킬,트렌드"

HEADER_RE = re.compile(r"^\[(.+?)\]\s*카카오톡 대화")
DATE_RE = re.compile(r"^-{3,}\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일.*-{3,}$")
MSG_RE = re.compile(r"^\[(.+?)\]\s*\[(오전|오후)\s*(\d{1,2}):(\d{2})\]\s*(.*)$")
# PC 카톡 내보내기 형식: 2026. 11. 7. 오전 8:50, 이름 : 본문
PC_MSG_RE = re.compile(r"^(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.\s*(오전|오후)\s*(\d{1,2}):(\d{2}),\s*(.+?)\s:\s(.*)$")
SYSTEM_RE = re.compile(r"님이 (들어왔|나갔)습니다|님을 초대했습니다|^(사진|동영상|이모티콘|삭제된 메시지입니다)\.?$")


def to_24h(ampm: str, hour: int) -> int:
    """오전/오후 12시간제를 24시간제로 바꾼다(오전 12시=0시, 오후 12시=12시)."""
    return hour % 12 + (12 if ampm == "오후" else 0)


def parse_chat_text(text: str) -> tuple[str | None, list[dict]]:
    """대화록 텍스트를 (방 이름, 메시지 목록)으로 파싱한다. 여러 줄 메시지는 이어 붙인다."""
    room: str | None = None
    year = month = day = None
    messages: list[dict] = []
    current: dict | None = None
    for line in text.splitlines():
        line = line.rstrip()
        if room is None and (m := HEADER_RE.match(line)):
            room = m.group(1)
            continue
        if m := DATE_RE.match(line):
            year, month, day = (int(g) for g in m.groups())
            current = None
            continue
        if m := PC_MSG_RE.match(line):
            y, mo, d, ampm, h, mi, sender, body = m.groups()
            current = _new_msg(int(y), int(mo), int(d), ampm, int(h), int(mi), sender, body)
            messages.append(current)
            continue
        if year and (m := MSG_RE.match(line)):
            sender, ampm, h, mi, body = m.groups()
            current = _new_msg(year, month, day, ampm, int(h), int(mi), sender, body)
            messages.append(current)
            continue
        if current is not None and line.strip():
            current["message"] += "\n" + line  # 직전 메시지의 다음 줄
    return room, [m for m in messages if not SYSTEM_RE.search(m["message"].strip())]


def _new_msg(y: int, mo: int, d: int, ampm: str, h: int, mi: int, sender: str, body: str) -> dict:
    """파싱된 한 건을 dict 로 만든다(시각은 KST 로 가정)."""
    try:
        sent = datetime(y, mo, d, to_24h(ampm, h), mi, tzinfo=KST)
    except ValueError:
        sent = datetime.now(KST)
    return {"sender": sender, "message": body, "sent_at": sent}


def read_text_file(path: Path) -> str:
    """UTF-8 → UTF-8(BOM) → CP949 순으로 디코딩을 시도한다."""
    raw = path.read_bytes()
    for enc in ("utf-8", "utf-8-sig", "cp949"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"인코딩을 알 수 없는 파일: {path.name}")


def is_priority_room(room: str) -> bool:
    """방 이름에 우선 키워드(AI, 에이전트, 스킬, 트렌드 등)가 들어 있는지."""
    words = env_list("KAKAO_PRIORITY_ROOM_KEYWORDS", DEFAULT_PRIORITY_ROOM_WORDS)
    return any(w.lower() in room.lower() for w in words)


def room_allowed(room: str) -> bool:
    """허용 목록이 비어 있으면 전체 수용, 있으면 목록에 있거나 우선 키워드 방만 허용."""
    allowed = env_list("KAKAO_ALLOWED_ROOMS")
    return not allowed or room in allowed or is_priority_room(room)


def make_source_id(room: str, sender: str, sent_at: datetime, text: str) -> str:
    """웹훅·파일 공통 중복 방지 키: sha1(방|발신자|분 단위 시각|본문) 앞 16자."""
    minute = sent_at.astimezone(KST).strftime("%Y-%m-%d %H:%M")
    return hashlib.sha1(f"{room}|{sender}|{minute}|{text}".encode("utf-8")).hexdigest()[:16]


def ingest_message(conn: sqlite3.Connection, room: str, sender: str, message: str,
                   sent_at: datetime) -> dict:
    """글 1건을 필터→점수화→저장한다. {'result': stored|duplicate|rejected, ...} 를 반환한다."""
    keywords = db.load_keywords(conn)
    verdict = classify(message, extra_keywords=[k for k in keywords if len(k) >= 2])
    if not verdict.passed:
        return {"result": "rejected", "reason": verdict.reason}
    text = mask_pii(verdict.text)
    sender = mask_pii(sender)[:40]
    first_line = text.split("\n")[0]
    url_match = URL_RE.search(text)
    published = sent_at.astimezone(timezone.utc).isoformat(timespec="seconds")
    score, hits = scorer.score_item(
        first_line, text[:200], 0, published, keywords,
        bonus=scorer.kakao_bonus(text, is_priority_room(room)),
    )
    item = {
        "source": "kakaotalk", "source_id": make_source_id(room, sender, sent_at, text),
        "title": first_line[:80], "url": url_match.group(0) if url_match else None,
        "summary": text[:200], "summary_ko": text[:200], "author": sender, "published_at": published,
        "score": score, "tags": ",".join(hits), "room": room,
        "filter_tags": ",".join(verdict.tags),
    }
    item_id = db.insert_item(conn, item)
    if item_id is None:
        return {"result": "duplicate"}
    return {"result": "stored", "id": item_id, "score": score}


class KakaoFileCollector(BaseCollector):
    """data/kakaotalk/*.txt 를 스캔한다. 변경 없는 파일은 file_cursors 로 건너뛴다."""

    name = "kakao_file"

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or CHAT_DIR

    def collect(self) -> dict:
        """모든 대화록을 파싱해 필터 통과 글을 저장한다(신규 0건이어도 ok)."""
        fetched = inserted = 0
        if not self.directory.is_dir():
            return {"fetched": 0, "inserted": 0}
        with db.get_conn() as conn:
            for path in sorted(self.directory.glob("*.txt")):
                stat = path.stat()
                row = conn.execute("SELECT size_bytes, mtime FROM file_cursors WHERE path=?", (str(path),)).fetchone()
                if row and row["size_bytes"] == stat.st_size and row["mtime"] == stat.st_mtime:
                    continue
                f, i = self._parse_file(conn, path)
                fetched, inserted = fetched + f, inserted + i
                conn.execute(
                    "INSERT OR REPLACE INTO file_cursors(path, size_bytes, mtime, parsed_at) VALUES (?,?,?,?)",
                    (str(path), stat.st_size, stat.st_mtime, db.now_iso()),
                )
        return {"fetched": fetched, "inserted": inserted}

    @staticmethod
    def _parse_file(conn: sqlite3.Connection, path: Path) -> tuple[int, int]:
        """파일 1개를 처리하고 (읽은 건수, 신규 저장 건수)를 반환한다."""
        room, messages = parse_chat_text(read_text_file(path))
        room = room or path.stem
        if not room_allowed(room):
            log.info("허용되지 않은 방이라 건너뜀: %s", room)
            return 0, 0
        stored = 0
        for m in messages:
            res = ingest_message(conn, room, m["sender"], m["message"], m["sent_at"])
            stored += res["result"] == "stored"
        return len(messages), stored
