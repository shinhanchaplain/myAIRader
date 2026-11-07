# AI Radar (myAIRadar)

## 목적
GitHub·Hacker News·GeekNews·arXiv 및 카카오톡 AI 오픈채팅방의 핵심 AI 동향/스킬/공지를 60초마다 자동 수집·점수화하여
대시보드와 Slack으로 알려주는 개인용 레이더. 강의 소재와 블로그 글감 공급이 목적.

## 기술 스택
- Backend: Python 3.12, FastAPI, sqlite3(표준), APScheduler, httpx
- Frontend: HTML + Tailwind CSS(CDN) + Vanilla JS (빌드 도구 없음)
- 실행: `uvicorn src.back.main:app --reload --port 8020`
- 테스트: `pytest -q`

## 구조
- `src/back/`: 백엔드 (`main.py`, `db.py`, `scheduler.py`, `scorer.py`, `routes.py`, `notifier.py`)
- `src/back/collectors/`: 소스별 수집기 (`base.py`, `github.py`, `hn.py`, `rss.py`, `arxiv.py`, `kakaotalk.py`)
- `data/kakaotalk/`: 카톡 대화 내보내기 텍스트 파일 저장 폴더
- `src/front/`: 대시보드 (`index.html`, `app.js`)
- `docs/`: 기획 및 분석 문서 (`PLAN.md`, `API.md`, `radar_analyze.md`)
- `tests/`: 테스트 코드 (`test_db.py`, `test_collectors.py`, `test_api.py`)

## 규칙 (필수)
1. 모든 주석·docstring·사용자 메시지는 한국어로 작성한다.
2. 비밀값은 `.env`에서만 읽는다. 코드·로그·커밋에 절대 포함하지 않는다.
3. 수집기는 예외를 삼키지 말고 `collect_runs`에 기록한다. 신규 0건이어도 `status=ok`로 남긴다.
4. 카카오톡 수집기는 `data/kakaotalk/*.txt`를 파싱하여 단순 잡담(인사, ㅋㅋ 등)은 제외하고, URL 포함 글이나 AI 키워드(프롬프트, 모델, 에이전트, 팁 등) 중심 정보만 필터링하여 저장한다.
5. 외부 호출은 타임아웃 10초, 재시도 2회(지수 백오프), `User-Agent: AIRadar/0.1 (education)` 명시.
6. 스케줄러 작업은 `max_instances=1`, `coalesce=True` (겹침 실행 방지).
7. 코드 수정 후에는 `pytest`와 서버 기동으로 직접 검증한다.
8. 큰 변경은 Plan 모드로 계획 → 승인 → 실행. 단계마다 `git commit`으로 백업한다.

## 금지 사항
- 개인정보·회사 기밀 수집, 로그인이 필요한 사이트 크롤링, 유료 API 호출
- 수집한 본문을 그대로 재게시하는 행위 (링크 + 짧은 요약만)
- 포트 8000 또는 8010 사용 금지 (반드시 8020 사용)
