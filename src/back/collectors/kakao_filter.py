"""카카오톡 글 필터: 잡담 탈락, URL/AI 키워드 글만 통과. 개인정보 마스킹 포함(순수 함수)."""
import re
from dataclasses import dataclass, field

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)
PHONE_RE = re.compile(r"(?<!\d)0\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{4}(?!\d)")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
LAUGH_RE = re.compile(r"[ㅋㅎㅠㅜ]")
GREETING_START_RE = re.compile(r"^(안녕|반갑|반가워|네+\b|넵|넹|ㅇㅇ|ㅇㅋ|오\b|와\b|대박|굿|좋은 아침|수고)")
THANKS_RE = re.compile(r"감사|고맙|고마워|땡큐|ㄳ")
NOTICE_RE = re.compile(r"공지|필독")

# AI 키워드 (대소문자 무시). keywords 테이블 값과 합쳐서 쓸 수 있다.
AI_KEYWORDS = [
    "claude", "클로드", "gpt", "chatgpt", "gemini", "llm", "프롬프트", "에이전트", "agent",
    "mcp", "모델", "꿀팁", "팁", "공지", "필독", "논문", "스킬", "코딩", "자동화", "rag",
    "codex", "anthropic", "openai",
]
MIN_KEYWORD_LEN = 20   # 키워드 통과에 필요한 최소 길이(공백 제외)
MIN_LEN = 10           # 이보다 짧으면 잡담
SHORT_REACTION_LEN = 50


@dataclass
class FilterResult:
    """분류 결과: 통과 여부, 사유(탈락 시 reason, 통과 시 tags), 정규화된 본문."""
    passed: bool
    reason: str = ""
    tags: list[str] = field(default_factory=list)
    text: str = ""


def normalize(text: str) -> str:
    """공백을 압축하고 ㅋ/ㅎ 반복을 줄인다."""
    text = re.sub(r"([ㅋㅎㅠㅜ])\1{2,}", r"\1\1", text)
    return re.sub(r"\s+", " ", text).strip()


def mask_pii(text: str) -> str:
    """전화번호와 이메일을 마스킹한다."""
    return EMAIL_RE.sub("[이메일]", PHONE_RE.sub("[전화번호]", text))


def _is_emoji_only(text: str) -> bool:
    """한글/영문/숫자가 하나도 없고 URL 도 없으면 이모지·기호만 있는 글로 본다."""
    return not re.search(r"[0-9A-Za-z가-힣]", text)


def classify(raw: str, extra_keywords: list[str] | None = None) -> FilterResult:
    """글을 분류한다. 순서: URL 통과 → 잡담 탈락 → 키워드 통과 → 기본 탈락."""
    text = normalize(raw or "")
    if not text:
        return FilterResult(False, "empty", text=text)
    compact = text.replace(" ", "")
    tags: list[str] = []
    has_url = bool(URL_RE.search(text))
    if NOTICE_RE.search(text):
        tags.append("notice")
    if has_url:
        return FilterResult(True, tags=["url", *tags], text=text)

    if _is_emoji_only(text):
        return FilterResult(False, "chitchat", text=text)
    if len(compact) < MIN_LEN:
        return FilterResult(False, "chitchat", text=text)
    if len(LAUGH_RE.findall(compact)) / len(compact) >= 0.5:
        return FilterResult(False, "chitchat", text=text)
    if len(text) < SHORT_REACTION_LEN and THANKS_RE.search(text):
        return FilterResult(False, "chitchat", text=text)
    if len(text) < 40 and GREETING_START_RE.search(text):
        return FilterResult(False, "chitchat", text=text)

    lowered = text.lower()
    if len(compact) >= MIN_KEYWORD_LEN:
        for kw in [*AI_KEYWORDS, *(extra_keywords or [])]:
            if kw.lower() in lowered:
                return FilterResult(True, tags=["keyword", *tags], text=text)
    return FilterResult(False, "no_signal", text=text)
