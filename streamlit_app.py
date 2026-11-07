"""AI Radar 스트림릿(Streamlit) 대시보드 - 사용자 선호 UI 디자인 적용 버전.
FastAPI 원본 대시보드의 미려하고 깔끔한 Tailwind 카드 디자인을 1:1로 재현합니다.
"""
import os
import sqlite3
import html
from datetime import datetime, timezone, timedelta
from pathlib import Path
import streamlit as st
from src.back.report import generate_today_top5_report

# 1. 페이지 설정
st.set_page_config(
    page_title="AI Radar 대시보드",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

ROOT_DIR = Path(__file__).resolve().parent
DB_PATH = os.environ.get("RADAR_DB_PATH") or str(ROOT_DIR / "data" / "radar.db")
KST = timezone(timedelta(hours=9))

# 2. 커스텀 CSS (Tailwind 스타일 및 깔끔한 대시보드 테마)
st.markdown("""
<style>
  /* 전체 페이지 배경 및 여백 설정 */
  .stApp {
    background-color: #f8fafc;
    color: #1e293b;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  }
  .block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 2rem !important;
    max-width: 1150px !important;
  }

  /* 스트림릿 기본 헤더/푸터 최소화 */
  header[data-testid="stHeader"] {
    background-color: transparent !important;
  }
  #MainMenu, footer {
    visibility: hidden;
  }

  /* 상단 상태 카드 디자인 */
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1rem;
    margin-bottom: 1.5rem;
  }
  @media (max-width: 768px) {
    .stats-grid {
      grid-template-columns: repeat(2, 1fr);
    }
  }
  .stat-card {
    background: #ffffff;
    border-radius: 1rem;
    padding: 1rem 1.25rem;
    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px -1px rgba(0, 0, 0, 0.05);
    border: 1px solid #f1f5f9;
  }
  .stat-title {
    font-size: 0.75rem;
    color: #64748b;
    font-weight: 500;
  }
  .stat-val {
    font-size: 1.5rem;
    font-weight: 700;
    color: #0f172a;
    margin-top: 0.25rem;
  }
  .stat-sub {
    font-size: 0.75rem;
    color: #94a3b8;
    margin-top: 0.25rem;
  }

  /* 프로그레스 바 */
  .gauge-bg {
    width: 100%;
    height: 8px;
    background-color: #e2e8f0;
    border-radius: 9999px;
    margin-top: 0.5rem;
    overflow: hidden;
  }
  .gauge-fill {
    height: 100%;
    background-color: #6366f1;
    border-radius: 9999px;
    width: 75%;
  }

  /* 피드 컨테이너 */
  .feed-container {
    background: #ffffff;
    border-radius: 1rem;
    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
    border: 1px solid #f1f5f9;
    overflow: hidden;
    margin-top: 1rem;
  }

  /* 피드 헤더 바 */
  .feed-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 1.25rem;
    border-bottom: 1px solid #f1f5f9;
  }

  /* 피드 아이템 */
  .feed-item {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 1.1rem 1.25rem;
    border-bottom: 1px solid #f1f5f9;
    transition: background-color 0.15s ease;
  }
  .feed-item:hover {
    background-color: #f8fafc;
  }
  .feed-item:last-child {
    border-bottom: none;
  }

  /* 뱃지 스타일 */
  .badge {
    display: inline-block;
    padding: 0.2rem 0.6rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 700;
    flex-shrink: 0;
    margin-top: 0.15rem;
  }
  .badge-github {
    background-color: #0f172a;
    color: #ffffff;
  }
  .badge-hn {
    background-color: #f97316;
    color: #ffffff;
  }
  .badge-kakao {
    background-color: #facc15;
    color: #451a03;
  }

  /* 타이틀 및 점수 */
  .item-title {
    font-size: 1rem;
    font-weight: 600;
    color: #1e293b;
    text-decoration: none;
    line-height: 1.4;
  }
  .item-title:hover {
    text-decoration: underline;
    color: #4f46e5;
  }
  .item-score {
    font-size: 0.875rem;
    font-weight: 700;
    color: #4f46e5;
    flex-shrink: 0;
    margin-left: auto;
    padding-left: 0.5rem;
  }

  /* 한글 요약 박스 */
  .ko-summary-box {
    margin-top: 0.45rem;
    padding: 0.6rem 0.85rem;
    background-color: #eef2ff;
    border-left: 4px solid #6366f1;
    border-radius: 0.5rem;
    font-size: 0.875rem;
    color: #1e293b;
    line-height: 1.55;
  }
  .ko-label {
    font-weight: 700;
    color: #4f46e5;
    margin-right: 0.4rem;
  }

  /* 본문 및 메타 */
  .item-desc {
    font-size: 0.875rem;
    color: #475569;
    margin-top: 0.35rem;
    line-height: 1.5;
  }
  .item-meta {
    font-size: 0.75rem;
    color: #94a3b8;
    margin-top: 0.35rem;
  }

  /* 접기/펼치기 details */
  details summary {
    outline: none;
    cursor: pointer;
    user-select: none;
    font-size: 0.75rem;
    color: #4f46e5;
    font-weight: 700;
    margin-top: 0.4rem;
    list-style: none;
  }
  details summary::-webkit-details-marker {
    display: none;
  }
</style>
""", unsafe_allow_html=True)


def get_connection():
    """SQLite DB 읽기 전용 연결."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def time_ago(iso_str: str) -> str:
    """ISO 문자열을 상대 시간(예: 5분 전, 1시간 전)으로 변환."""
    if not iso_str:
        return ""
    try:
        t = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = (now - t).total_seconds()
        if diff < 60:
            return f"{max(int(diff), 1)}초 전"
        if diff < 3600:
            return f"{int(diff // 60)}분 전"
        if diff < 86400:
            return f"{int(diff // 3600)}시간 전"
        return f"{int(diff // 86400)}일 전"
    except Exception:
        return iso_str[:10]


def load_stats_data():
    """대시보드 상단 통계 수치 로드."""
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        kakao_count = conn.execute("SELECT COUNT(*) FROM items WHERE source = 'kakaotalk'").fetchone()[0]
        github_count = conn.execute("SELECT COUNT(*) FROM items WHERE source = 'github'").fetchone()[0]
        hn_count = conn.execute("SELECT COUNT(*) FROM items WHERE source = 'hn'").fetchone()[0]

        # 24시간 내 신규 수집 수
        since_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        new_24h = conn.execute("SELECT COUNT(*) FROM items WHERE first_seen_at >= ?", (since_24h,)).fetchone()[0]

        # 최근 1시간 성공률
        since_1h = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        runs_1h = conn.execute(
            "SELECT COUNT(*), SUM(CASE WHEN status='ok' THEN 1 ELSE 0 END) FROM collect_runs WHERE started_at >= ?",
            (since_1h,)
        ).fetchone()
        total_runs = runs_1h[0] or 0
        ok_runs = runs_1h[1] or 0
        success_rate = round(ok_runs / total_runs * 100, 1) if total_runs else 100.0

        # 오늘 슬랙 발송 수
        midnight = datetime.now(KST).replace(hour=0, minute=0, second=0, microsecond=0)
        start_utc = midnight.astimezone(timezone.utc).isoformat(timespec="seconds")
        slack_sent = conn.execute("SELECT COUNT(*) FROM items WHERE notified_at >= ?", (start_utc,)).fetchone()[0]

    return {
        "total": total,
        "new_24h": new_24h,
        "github": github_count,
        "hn": hn_count,
        "kakao": kakao_count,
        "success_rate": success_rate,
        "slack_sent": slack_sent,
    }


def load_feed_items(source: str, min_score: float, limit: int = 50):
    """조건에 부합하는 피드 아이템 로드."""
    sql = "SELECT * FROM items WHERE score >= ?"
    args = [min_score]
    if source:
        sql += " AND source = ?"
        args.append(source)
    sql += " ORDER BY first_seen_at DESC, score DESC LIMIT ?"
    args.append(limit)

    with get_connection() as conn:
        rows = conn.execute(sql, args).fetchall()
        return [dict(r) for r in rows]


# --- 상단 헤더 ---
now_kst = datetime.now(KST).strftime("%Y. %m. %d. %p %I:%M:%S").replace("AM", "오전").replace("PM", "오후")
header_html = (
    '<div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 1rem;">'
    '<div>'
    '<h1 style="font-size: 1.6rem; font-weight: 800; color: #0f172a; margin: 0; display: inline-flex; align-items: center; gap: 0.5rem;">'
    '📡 AI Radar'
    '</h1>'
    '<p style="font-size: 0.85rem; color: #64748b; margin: 0.2rem 0 0 0;">'
    'GitHub · Hacker News · 카카오톡 AI 오픈채팅 동향 레이더'
    '</p>'
    '</div>'
    f'<div style="font-size: 0.75rem; color: #94a3b8;">{now_kst}</div>'
    '</div>'
)
st.markdown(header_html, unsafe_allow_html=True)


# --- 20초 자동 갱신 실시간 대시보드 조각 (Fragment) ---
@st.fragment(run_every="20s")
def render_dashboard_content():
    stats = load_stats_data()

    # 4개 통계 카드
    stats_html = (
        '<div class="stats-grid">'
        '<div class="stat-card">'
        '<div class="stat-title">수집 상태</div>'
        '<div class="stat-val" style="color: #059669;">🟢 정상</div>'
        '<div class="stat-sub">20초마다 자동 갱신</div>'
        '</div>'
        '<div class="stat-card">'
        '<div class="stat-title">다음 수집까지</div>'
        '<div class="stat-val">20 <span style="font-size: 1rem; font-weight: 400; color: #94a3b8;">초</span></div>'
        '<div class="gauge-bg"><div class="gauge-fill"></div></div>'
        '</div>'
        '<div class="stat-card">'
        '<div class="stat-title">24시간 신규 / 전체</div>'
        f'<div class="stat-val">{stats["new_24h"]:,} <span style="font-size: 1rem; font-weight: 400; color: #94a3b8;">/ {stats["total"]:,}</span></div>'
        f'<div class="stat-sub">GitHub {stats["github"]} · HN {stats["hn"]} · 카톡 {stats["kakao"]}</div>'
        '</div>'
        '<div class="stat-card">'
        '<div class="stat-title">수집 성공률 (1시간)</div>'
        f'<div class="stat-val">{stats["success_rate"]}%</div>'
        f'<div class="stat-sub">Slack 오늘 {stats["slack_sent"]}/300건</div>'
        '</div>'
        '</div>'
    )
    st.markdown(stats_html, unsafe_allow_html=True)

    # 오늘 TOP 5 보고서 생성 버튼 및 미리보기 섹션
    col_head_title, col_head_btn = st.columns([3, 1.4])
    with col_head_title:
        st.markdown('<div style="font-size: 1.15rem; font-weight: 700; color: #0f172a; margin-top: 0.2rem;">실시간 피드</div>', unsafe_allow_html=True)
    with col_head_btn:
        if st.button("📊 오늘 TOP 5 정리 & 저장", use_container_width=True, help="오늘 최고 점수 받은 글 5개씩(전체글 및 카카오톡) 정리하여 .md 파일로 저장합니다."):
            with st.spinner("오늘의 인기글 TOP 5를 추출 및 정리하는 중..."):
                rep_content, rep_path, rep_data = generate_today_top5_report()
                st.session_state["top5_report"] = rep_content
                st.session_state["top5_file_path"] = rep_path
                st.success("✅ 오늘 TOP 5 브리핑 리포트가 성공적으로 저장되었습니다!")

    if st.session_state.get("top5_report"):
        with st.expander("📋 [일일 브리핑] 오늘 최고 인기글 TOP 5 마크다운 리포트", expanded=True):
            st.markdown(st.session_state["top5_report"])
            col_down1, col_down2 = st.columns([2, 1])
            with col_down1:
                st.caption(f"📁 저장 파일: `{st.session_state.get('top5_file_path')}`")
            with col_down2:
                file_ts = datetime.now(KST).strftime('%Y%m%d_%H%M%S')
                st.download_button(
                    "💾 마크다운(.md) 다운로드",
                    data=st.session_state["top5_report"],
                    file_name=f"AI_Radar_Top5_{file_ts}.md",
                    mime="text/markdown",
                    use_container_width=True,
                )

    # 필터 컨트롤 (상단 탭 형식)
    col_filter1, col_filter2 = st.columns([3, 2])
    with col_filter1:
        source_tab = st.pills(
            "출처 선택",
            options=["전체", "카카오톡", "GitHub", "Hacker News"],
            default="전체",
            label_visibility="collapsed",
        )
    with col_filter2:
        score_tab = st.pills(
            "점수 필터",
            options=["⭐ 10점 이상 추천글", "📜 전체 글 보기 (낮은 점수 포함)"],
            default="⭐ 10점 이상 추천글",
            label_visibility="collapsed",
        )

    source_map = {"전체": "", "카카오톡": "kakaotalk", "GitHub": "github", "Hacker News": "hn"}
    selected_source = source_map.get(source_tab, "")
    min_score = 10.0 if "10점" in (score_tab or "") else 0.0

    items = load_feed_items(source=selected_source, min_score=min_score, limit=50)

    # 피드 리스트 렌더링
    feed_html_list = []
    feed_html_list.append('<div class="feed-container">')

    if not items:
        feed_html_list.append('<div style="padding: 2.5rem; text-align: center; color: #94a3b8; font-size: 0.875rem;">조건에 일치하는 글이 없습니다.</div>')
    else:
        for it in items:
            src = it.get("source", "")
            if src == "github":
                badge_html = '<span class="badge badge-github">GitHub</span>'
            elif src == "hn":
                badge_html = '<span class="badge badge-hn">Hacker News</span>'
            else:
                badge_html = '<span class="badge badge-kakao">카톡</span>'

            title_text = html.escape(it.get("title") or "제목 없음")
            url = it.get("url")
            if url:
                safe_url = html.escape(url)
                title_elem = f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer" class="item-title">{title_text}</a>'
            else:
                title_elem = f'<span class="item-title">{title_text}</span>'

            score_elem = f'<span class="item-score">{it.get("score", 0):.2f}점</span>'

            # 한글 요약 상자
            ko_summary = (it.get("summary_ko") or "").strip()
            orig_summary = (it.get("summary") or "").strip()
            ko_box_html = ""
            if ko_summary and ko_summary != orig_summary and ko_summary != it.get("title"):
                safe_ko = html.escape(ko_summary)
                ko_box_html = f'<div class="ko-summary-box"><span class="ko-label">🇰🇷 한글 요약:</span> {safe_ko}</div>'

            # 본문 및 접기/펼치기
            desc_html = ""
            if orig_summary and orig_summary != it.get("title"):
                safe_desc = html.escape(orig_summary)
                if len(safe_desc) > 80 or "\n" in safe_desc or src == "kakaotalk":
                    short_desc = safe_desc[:80] + "..."
                    desc_html = (
                        f'<div class="item-desc">{short_desc}</div>'
                        f'<details><summary>전체 보기 ▼</summary>'
                        f'<div class="item-desc" style="white-space: pre-wrap; margin-top: 0.4rem; padding: 0.5rem; background: #f8fafc; border-radius: 0.375rem;">{safe_desc}</div>'
                        f'</details>'
                    )
                else:
                    desc_html = f'<div class="item-desc">{safe_desc}</div>'

            # 메타 정보 (작성자, 방 이름, 별점, 시간)
            meta_parts = []
            if it.get("room"):
                meta_parts.append(f"⚑ {html.escape(it['room'])}")
            if it.get("author"):
                meta_parts.append(html.escape(it["author"]))
            if it.get("stars"):
                meta_parts.append(f"★ {it['stars']}")
            meta_parts.append(time_ago(it.get("first_seen_at")))
            meta_str = " · ".join(meta_parts)
            meta_html = f'<div class="item-meta">{meta_str}</div>'

            item_html = (
                f'<div class="feed-item">'
                f'{badge_html}'
                f'<div style="flex-grow: 1; min-width: 0;">'
                f'<div style="display: flex; align-items: baseline; justify-content: space-between;">'
                f'{title_elem}{score_elem}'
                f'</div>'
                f'{ko_box_html}'
                f'{desc_html}'
                f'{meta_html}'
                f'</div>'
                f'</div>'
            )
            feed_html_list.append(item_html)

    feed_html_list.append('</div>')
    st.markdown("".join(feed_html_list), unsafe_allow_html=True)


render_dashboard_content()
