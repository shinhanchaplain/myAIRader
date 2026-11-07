# AI Radar (myAIRadar)

GitHub·Hacker News 및 카카오톡 AI 오픈채팅방의 AI 동향/스킬/공지를 60초마다 자동 수집·점수화하여
대시보드와 Slack으로 알려주는 개인용 레이더입니다. 강의 소재와 블로그 글감 공급이 목적입니다.

> 현재 구현된 수집기: GitHub, Hacker News, 카카오톡. GeekNews(RSS)·arXiv 수집기는 계획 단계입니다. (`docs/PLAN.md` 참고)

## 기술 스택

- Backend: Python, FastAPI, sqlite3(표준), APScheduler, httpx
- Frontend: HTML + Tailwind CSS(CDN) + Vanilla JS (빌드 도구 없음)
- 테스트: pytest

## 빠른 시작

```bash
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env
uvicorn src.back.main:app --reload --port 8020
```

브라우저에서 <http://localhost:8020> 으로 대시보드를 엽니다. 포트는 반드시 **8020**을 사용합니다.

## 환경 변수 (`.env`)

비밀값은 `.env`에서만 읽으며 저장소에 커밋하지 않습니다. 모든 항목은 선택 사항입니다.

| 변수 | 설명 |
| --- | --- |
| `GITHUB_TOKEN` | GitHub 개인 액세스 토큰 (미입력 시 Search API 분당 10회 제한) |
| `SLACK_BOT_TOKEN`, `SLACK_CHANNEL_ID` | Slack 알림 설정 |
| `SLACK_MIN_SCORE`, `SLACK_DAILY_LIMIT` | Slack 알림 기준 점수 / 일일 최대 건수 |
| `KAKAO_WEBHOOK_SECRET` | 카카오톡 웹훅 인증 시크릿 |
| `KAKAO_ALLOWED_ROOMS` | 허용 방 이름(쉼표 구분). 비우면 전체 허용 |
| `KAKAO_PRIORITY_ROOM_KEYWORDS` | 우선 방 키워드(쉼표 구분) |

## API

모든 경로는 `/api` 아래에 있습니다.

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| GET | `/api/health` | 서버 상태 확인 |
| GET | `/api/items` | 수집된 항목 목록 |
| GET | `/api/runs` | 수집 실행 이력 (`collect_runs`) |
| GET | `/api/stats` | 통계 |
| POST | `/api/collect/run` | 수집 수동 실행 |
| POST | `/api/notify/test` | Slack 테스트 알림 |
| POST | `/api/webhook/kakao` | 카카오톡 웹훅 수신 |

## 카카오톡 수집

`data/kakaotalk/*.txt`(대화 내보내기 파일)를 파싱하며, 단순 잡담은 제외하고 URL 포함 글이나
AI 키워드(프롬프트, 모델, 에이전트, 팁 등) 중심 정보만 저장합니다.
웹훅 전송 예시는 `scripts/send_kakao_webhook.py`를 참고하세요.

## 프로젝트 구조

```
src/back/              백엔드 (main, db, scheduler, scorer, routes, notifier, config)
src/back/collectors/   소스별 수집기 (base, github, hn, kakaotalk, kakao_filter)
src/front/             대시보드 (index.html, app.js)
data/kakaotalk/        카톡 대화 내보내기 텍스트 저장 폴더
scripts/               보조 스크립트
docs/                  기획 문서 (PLAN.md)
tests/                 테스트 코드
```

## 테스트

```bash
pytest -q
```

## 운영 원칙

- 수집기는 실패를 삼키지 않고 `collect_runs`에 기록하며, 신규 0건이어도 `status=ok`로 남깁니다.
- 외부 호출은 타임아웃 10초, 재시도 2회(지수 백오프), `User-Agent: AIRadar/0.1 (education)`을 사용합니다.
- 스케줄러 작업은 `max_instances=1`, `coalesce=True`로 겹침 실행을 막습니다.
- 수집한 본문은 재게시하지 않고 링크와 짧은 요약만 다룹니다.
