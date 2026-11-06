# 코딩 표준 및 규칙 (Code Standards)

1. **언어 및 주석**:
   - 모든 주석, docstring, 로깅 메시지, 사용자 인터페이스 텍스트는 한국어로 작성합니다.
   - 변수명 및 함수명은 표준 Python 규칙(snake_case)을 따릅니다.
   - 클래스명은 PascalCase를 따릅니다.

2. **함수 및 모듈 설계**:
   - 모든 공개 함수는 입력/출력 타입 힌트와 간결한 docstring을 포함해야 합니다.
   - 함수는 단일 책임 원칙(SRP)을 준수하며 가급적 50줄 이내로 유지합니다.

3. **예외 처리 및 안전성**:
   - `except Exception:`과 같은 포괄적 예외 처리를 지양하고 구체적인 예외 타입(`httpx.TimeoutException`, `sqlite3.IntegrityError` 등)을 명시합니다.
   - 네트워크 통신이나 파일 I/O는 반드시 타임아웃과 예외 복구(Fallback) 로직을 갖춥니다.
   - 수집 실패 시 예외를 조용히 무시하지 않고, 반드시 로그 및 `collect_runs` 테이블에 기록합니다.

4. **비밀값 관리**:
   - 토큰, API 키, 웹훅 URL 등은 절대 코드 내에 하드코딩하지 않으며 `python-dotenv`를 통해 `.env`에서 로드합니다.
