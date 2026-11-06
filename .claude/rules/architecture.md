# 아키텍처 규칙 (Architecture Rules)

1. **프론트엔드 / 백엔드 분리**:
   - `src/back/`: 순수 Python 백엔드 (FastAPI, SQLite, APScheduler, httpx).
   - `src/front/`: 순수 정적 웹 에셋 (HTML + Tailwind CSS CDN + Vanilla JS). 별도의 Node.js 번들러/빌드 도구 없음.

2. **수집기 모듈 설계**:
   - 모든 수집기는 `src/back/collectors/base.py`의 `BaseCollector` 추상 클래스를 상속받아 `collect() -> dict` 메서드를 구현해야 합니다.
   - 수집 결과는 공통 스키마(items 테이블 컬럼)에 맞게 정규화하여 반환합니다.

3. **중복 방지 및 멱등성**:
   - SQLite DB의 `items` 테이블은 `UNIQUE(source, source_id)` 복합 유니크 제약 조건을 기반으로 중복 저장을 원천 차단합니다.
   - `INSERT OR IGNORE` 구문을 사용하여 멱등성을 보장합니다.

4. **스케줄러와 하트비트**:
   - APScheduler 작업은 `max_instances=1`, `coalesce=True`를 필수 적용하여 작업 지연으로 인한 겹침 실행을 방지합니다.
   - 신규 수집 데이터가 0건이어도 `collect_runs` 테이블에 수집 시각과 `status='ok'`(하트비트)를 반드시 남깁니다.

5. **포트 정책**:
   - 서버는 반드시 포트 `8020`으로 구동합니다 (`uvicorn src.back.main:app --reload --port 8020`).
