"""AI Radar 스트림릿(Streamlit) 실시간 대시보드 웹 앱 (20초 자동 갱신 지원)."""
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import streamlit as st

# 페이지 설정
st.set_page_config(
    page_title="AI Radar 대시보드",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT_DIR = Path(__file__).resolve().parent
DB_PATH = os.environ.get("RADAR_DB_PATH") or str(ROOT_DIR / "data" / "radar.db")


def get_connection():
    """SQLite DB 읽기 전용 연결."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def load_stats():
    """상단 통계 지표 로드."""
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        top_count = conn.execute("SELECT COUNT(*) FROM items WHERE score >= 10").fetchone()[0]
        kakao_count = conn.execute("SELECT COUNT(*) FROM items WHERE source = 'kakaotalk'").fetchone()[0]
        github_count = conn.execute("SELECT COUNT(*) FROM items WHERE source = 'github'").fetchone()[0]
        hn_count = conn.execute("SELECT COUNT(*) FROM items WHERE source = 'hn'").fetchone()[0]
    return {
        "total": total,
        "top": top_count,
        "kakao": kakao_count,
        "github": github_count,
        "hn": hn_count,
    }


def load_items(min_score: float = 0.0, source: str = "", query: str = "", limit: int = 60):
    """조건별 피드 아이템 조회."""
    sql = "SELECT * FROM items WHERE score >= ?"
    args = [min_score]
    if source:
        sql += " AND source = ?"
        args.append(source)
    if query:
        sql += " AND (title LIKE ? OR summary LIKE ? OR summary_ko LIKE ?)"
        args.extend([f"%{query}%", f"%{query}%", f"%{query}%"])
    sql += " ORDER BY first_seen_at DESC, score DESC LIMIT ?"
    args.append(limit)

    with get_connection() as conn:
        rows = conn.execute(sql, args).fetchall()
        return [dict(r) for r in rows]


# --- 사이드바 ---
st.sidebar.title("📡 AI Radar 컨트롤")
st.sidebar.markdown("GitHub · Hacker News · 카카오톡 동향 레이더")

# 1. 점수 필터 (토글)
score_mode = st.sidebar.radio(
    "🎯 점수 필터",
    ["⭐ 10점 이상 추천글 (기본)", "📜 전체 글 보기 (낮은 점수 포함)"],
    index=0,
)
min_score = 10.0 if "10점" in score_mode else 0.0

# 2. 출처 선택
source_choice = st.sidebar.selectbox(
    "📁 출처 필터",
    ["전체", "GitHub", "Hacker News", "카카오톡"],
    index=0,
)
source_map = {"전체": "", "GitHub": "github", "Hacker News": "hn", "카카오톡": "kakaotalk"}
selected_source = source_map[source_choice]

# 3. 검색어 입력
search_query = st.sidebar.text_input("🔍 키워드 검색", placeholder="예: claude, agent, 모델")

st.sidebar.divider()
st.sidebar.caption("⏱️ 20초마다 최신 글이 자동으로 갱신됩니다.")

# --- 메인 영역 ---
st.title("🛰️ AI Radar 실시간 트렌드 대시보드")
st.caption("AI 에이전트, MCP, LLM 및 오픈채팅방 실시간 정보 수집기")


# 20초마다 자동 갱신되는 실시간 피드 섹션
@st.fragment(run_every="20s")
def live_dashboard():
    # 통계 메트릭 표시
    stats = load_stats()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("총 수집 항목", f"{stats['total']:,} 건")
    with col2:
        st.metric("🔥 10점 이상 추천글", f"{stats['top']:,} 건", delta="엄선 알짜")
    with col3:
        st.metric("카카오톡 정보", f"{stats['kakao']} 건", delta="실시간 톡방")
    with col4:
        st.metric("오픈소스 (GitHub/HN)", f"{stats['github'] + stats['hn']:,} 건")

    st.divider()

    # 피드 아이템 로드
    items = load_items(min_score=min_score, source=selected_source, query=search_query)

    col_h1, col_h2 = st.columns([4, 1])
    with col_h1:
        st.subheader(f"실시간 피드 ({len(items)}건 표시)")
    with col_h2:
        now_str = datetime.now().strftime("%H:%M:%S")
        st.caption(f"🔄 갱신시각: {now_str}")

    if min_score >= 10.0:
        st.info("💡 현재 **10점 이상의 핵심 추천글**만 표시 중입니다. 더 많은 글을 보시려면 사이드바에서 '전체 글 보기'를 선택하세요.")

    if not items:
        st.warning("조건에 맞는 수집 항목이 없습니다.")
    else:
        for it in items:
            with st.container():
                src_label = {"github": "🐙 GitHub", "hn": "📰 Hacker News", "kakaotalk": "💬 카카오톡"}.get(it["source"], it["source"])
                score_color = "🔥" if it["score"] >= 10 else "⭐"

                col_title, col_score = st.columns([5, 1])
                with col_title:
                    if it.get("url"):
                        st.markdown(f"#### [{it['title']}]({it['url']})")
                    else:
                        st.markdown(f"#### {it['title']}")
                with col_score:
                    st.markdown(f"**{score_color} {it['score']:.1f}점**")

                ko_summary = (it.get("summary_ko") or "").strip()
                if ko_summary and ko_summary != (it.get("summary") or "").strip() and ko_summary != it["title"]:
                    st.success(f"🇰🇷 **한글 요약:** {ko_summary}")

                content = (it.get("summary") or "").strip()
                if content and content != it["title"]:
                    if len(content) > 100 or it["source"] == "kakaotalk":
                        with st.expander("📖 전체 본문 읽기 / 펼쳐보기"):
                            st.markdown(content)
                    else:
                        st.write(content)

                meta_parts = [f"**출처:** {src_label}"]
                if it.get("room"):
                    meta_parts.append(f"**채팅방:** {it['room']}")
                if it.get("author"):
                    meta_parts.append(f"**작성자:** {it['author']}")
                if it.get("stars"):
                    meta_parts.append(f"★ {it['stars']:,}")
                if it.get("first_seen_at"):
                    meta_parts.append(f"수집 시각: {it['first_seen_at'][:19].replace('T', ' ')}")

                st.caption(" · ".join(meta_parts))
                st.divider()


live_dashboard()
