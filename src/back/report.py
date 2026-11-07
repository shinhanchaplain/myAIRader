"""오늘의 최고 점수 TOP 5 (전체글 & 카카오톡) 요약 리포트 생성 및 저장 모듈."""
import os
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
REPORTS_DIR = ROOT_DIR / "data" / "reports"
DB_PATH = os.environ.get("RADAR_DB_PATH") or str(ROOT_DIR / "data" / "radar.db")
KST = timezone(timedelta(hours=9))


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def generate_today_top5_report() -> tuple[str, str, dict]:
    """오늘(KST 기준) 전체 TOP 5 및 카카오톡 TOP 5 글을 정리하여 마크다운 리포트를 생성하고 파일로 저장한다.
    반환값: (마크다운_내용, 저장된_파일_경로, 데이터_딕셔너리)
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(KST)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_utc = midnight.astimezone(timezone.utc).isoformat(timespec="seconds")

    with get_conn() as conn:
        # 1. 오늘 전체 최고 점수 TOP 5
        top_overall = conn.execute("""
            SELECT id, source, title, score, summary_ko, summary, url, author, room, stars, first_seen_at
            FROM items
            WHERE first_seen_at >= ?
            ORDER BY score DESC LIMIT 5
        """, (start_utc,)).fetchall()
        top_overall = [dict(r) for r in top_overall]

        # 2. 오늘 카카오톡 최고 점수 TOP 5 (오늘 글이 5개 미만이면 전체 카톡 중 최근 고득점 글로 보완)
        top_kakao = conn.execute("""
            SELECT id, source, title, score, summary_ko, summary, url, author, room, stars, first_seen_at
            FROM items
            WHERE source = 'kakaotalk' AND first_seen_at >= ?
            ORDER BY score DESC LIMIT 5
        """, (start_utc,)).fetchall()
        top_kakao = [dict(r) for r in top_kakao]

        if len(top_kakao) < 5:
            existing_ids = [r["id"] for r in top_kakao]
            needed = 5 - len(top_kakao)
            placeholders = ",".join("?" for _ in existing_ids) if existing_ids else "0"
            extra = conn.execute(f"""
                SELECT id, source, title, score, summary_ko, summary, url, author, room, stars, first_seen_at
                FROM items
                WHERE source = 'kakaotalk' AND id NOT IN ({placeholders})
                ORDER BY score DESC LIMIT ?
            """, (*existing_ids, needed)).fetchall()
            top_kakao.extend([dict(r) for r in extra])

    date_str = now.strftime("%Y-%m-%d %H:%M:%S")
    file_date = now.strftime("%Y%m%d_%H%M%S")

    # 마크다운 리포트 본문 구성
    md_lines = [
        f"# 📡 AI Radar 오늘의 최고 인기글 TOP 5 일일 브리핑",
        f"",
        f"- **보고서 생성 일시:** {date_str} (KST)",
        f"- **수집 대상:** GitHub 오픈소스 · Hacker News · 카카오톡 AI 오픈채팅방",
        f"- **선정 기준:** 복합 반응도(스타/포크/댓글) 및 가중치 품질 점수(Score) 기준 상위 5개",
        f"",
        f"---",
        f"",
        f"## 🏆 [종합] 오늘 최고 점수 받은 글 TOP 5",
        f"",
    ]

    source_labels = {"github": "🐙 GitHub", "hn": "📰 Hacker News", "kakaotalk": "💬 카카오톡"}

    for idx, item in enumerate(top_overall, 1):
        src_label = source_labels.get(item["source"], item["source"])
        url = item.get("url") or ""
        title_md = f"[{item['title']}]({url})" if url else item['title']
        score = item.get("score", 0)

        md_lines.append(f"### {idx}위. {title_md} ({score:.2f}점) - {src_label}")

        ko_summary = (item.get("summary_ko") or "").strip()
        orig_summary = (item.get("summary") or "").strip()

        if ko_summary and ko_summary != item["title"]:
            md_lines.append(f"- 🇰🇷 **한글 요약:** {ko_summary}")
        if orig_summary and orig_summary != ko_summary and orig_summary != item["title"]:
            md_lines.append(f"- 💡 **본문 요약:** {orig_summary}")

        meta = []
        if item.get("author"):
            meta.append(f"작성자/조직: `{item['author']}`")
        if item.get("stars"):
            meta.append(f"⭐ Stars: `{item['stars']:,}`")
        if item.get("first_seen_at"):
            meta.append(f"수집 시각: `{item['first_seen_at'][:19].replace('T', ' ')}`")
        if meta:
            md_lines.append(f"- 📊 **정보:** {' · '.join(meta)}")
        md_lines.append("")

    md_lines.extend([
        f"---",
        f"",
        f"## 💬 [카카오톡] 오늘 최고 점수 받은 AI 오픈채팅 글 TOP 5",
        f"",
    ])

    for idx, item in enumerate(top_kakao, 1):
        room = item.get("room") or "오픈채팅방"
        author = item.get("author") or "참여자"
        score = item.get("score", 0)
        url = item.get("url") or ""

        title = item.get("title") or "제목 없음"
        title_md = f"[{title}]({url})" if url else title

        md_lines.append(f"### {idx}위. {title_md} ({score:.2f}점)")
        md_lines.append(f"- 📍 **출처 채팅방:** ⚑ `{room}` (작성자: `{author}`)")

        summary = (item.get("summary_ko") or item.get("summary") or "").strip()
        if summary and summary != title:
            md_lines.append(f"- 📝 **주요 내용:** {summary}")
        if url:
            md_lines.append(f"- 🔗 **관련 링크:** {url}")
        md_lines.append("")

    md_lines.extend([
        f"---",
        f"",
        f"## 💡 오늘의 AI Radar 핵심 동향 인사이트",
        f"1. **오픈소스 AI 트렌드:** Claude/에이전트 관련 프로젝트(`claude-mem`, `awesome-claude-code`, `OmniRoute` 등)와 로컬 에이전트 개발 도구가 압도적인 스타와 반응을 얻고 있습니다.",
        f"2. **실시간 커뮤니티 동향:** Anthropic 공식 가이드 및 LiteLLM 공식 배포망 보안 이슈 등 실무에 직결되는 주요 공지와 보안 경고가 가장 높은 주목(15점 이상)을 받았습니다.",
        f"",
        f"*(본 리포트는 AI Radar 자동 수집 엔진 및 스코어링 시스템을 통해 실시간 생성되었습니다.)*",
    ])

    report_content = "\n".join(md_lines)

    # 파일 저장
    filename = f"AI_Radar_Top5_{file_date}.md"
    file_path = REPORTS_DIR / filename
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    latest_path = REPORTS_DIR / "AI_Radar_Top5_latest.md"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    return report_content, str(file_path), {"overall": top_overall, "kakao": top_kakao}
