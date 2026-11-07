"""DB 중복 방지와 기본 키워드 시드 테스트."""
from src.back import db


def _item(**kw):
    base = {"source": "hn", "source_id": "1", "title": "t", "score": 1.0}
    return {**base, **kw}


def test_같은_키는_한_건만_저장(temp_db):
    with db.get_conn() as conn:
        assert db.insert_item(conn, _item()) is not None
        assert db.insert_item(conn, _item()) is None
        assert conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 1


def test_소스가_다르면_별도_저장(temp_db):
    with db.get_conn() as conn:
        db.insert_item(conn, _item())
        assert db.insert_item(conn, _item(source="github")) is not None


def test_기본_키워드_시드(temp_db):
    with db.get_conn() as conn:
        assert "claude" in db.load_keywords(conn)


def test_수집_로그_기록(temp_db):
    db.record_run("hn", db.now_iso(), 5, 0, 0, "ok")
    assert db.query_runs()[0]["status"] == "ok"
