"""FAB-SENTINEL Streamlit 대시보드."""

from __future__ import annotations

import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

import api_client as api

st.set_page_config(
    page_title="FAB-SENTINEL",
    page_icon="🏭",
    layout="wide",
)

# ── 글로벌 CSS ──

st.markdown("""
<style>
/* 전체 배경 */
.stApp { background-color: #0a0f1a; }

/* 사이드바 */
section[data-testid="stSidebar"] {
    background-color: #111827;
    border-right: 1px solid #1f2937;
}
section[data-testid="stSidebar"] .stMarkdown h1 {
    background: linear-gradient(135deg, #10b981, #3b82f6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 1.6rem;
    letter-spacing: -0.5px;
}

/* 메트릭 카드 */
div[data-testid="stMetric"] {
    background: linear-gradient(135deg, #111827, #1a2332);
    border: 1px solid #1f2937;
    border-radius: 12px;
    padding: 16px 20px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.3);
}
div[data-testid="stMetric"] label {
    color: #9ca3af !important;
    font-size: 0.85rem !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    font-size: 2rem !important;
    font-weight: 700 !important;
}

/* KPI 카드 색상 */
.kpi-danger div[data-testid="stMetricValue"] { color: #ef4444 !important; }
.kpi-warning div[data-testid="stMetricValue"] { color: #f59e0b !important; }
.kpi-info div[data-testid="stMetricValue"] { color: #3b82f6 !important; }
.kpi-success div[data-testid="stMetricValue"] { color: #10b981 !important; }

/* 데이터프레임 */
div[data-testid="stDataFrame"] {
    border: 1px solid #1f2937;
    border-radius: 8px;
    overflow: hidden;
}

/* 섹션 헤더 */
.section-header {
    font-size: 1.1rem;
    font-weight: 600;
    color: #e5e7eb;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 2px solid #1f2937;
    display: flex;
    align-items: center;
    gap: 8px;
}
.section-header .icon {
    font-size: 1.2rem;
}

/* 상태 뱃지 */
.badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 600;
    letter-spacing: 0.3px;
}
.badge-critical { background: #7f1d1d; color: #fca5a5; border: 1px solid #dc2626; }
.badge-warning { background: #78350f; color: #fcd34d; border: 1px solid #d97706; }
.badge-detected { background: #7f1d1d; color: #fca5a5; }
.badge-acknowledged { background: #78350f; color: #fcd34d; }
.badge-investigating { background: #1e3a5f; color: #93c5fd; }
.badge-resolved { background: #064e3b; color: #6ee7b7; }
.badge-done { background: #064e3b; color: #6ee7b7; }
.badge-pending { background: #374151; color: #9ca3af; }
.badge-processing { background: #1e3a5f; color: #93c5fd; }
.badge-failed { background: #7f1d1d; color: #fca5a5; }

/* 상세 카드 */
.detail-card {
    background: #111827;
    border: 1px solid #1f2937;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 12px;
}
.detail-row {
    display: flex;
    justify-content: space-between;
    padding: 6px 0;
    border-bottom: 1px solid #1f293766;
}
.detail-label { color: #9ca3af; font-size: 0.85rem; }
.detail-value { color: #f3f4f6; font-weight: 500; }

/* 사이클 카드 */
.cycle-card {
    background: linear-gradient(135deg, #111827, #1a2332);
    border: 1px solid #1f2937;
    border-radius: 12px;
    padding: 20px;
    text-align: center;
}
.cycle-value {
    font-size: 2rem;
    font-weight: 700;
    color: #10b981;
}
.cycle-label {
    color: #9ca3af;
    font-size: 0.8rem;
    text-transform: uppercase;
    margin-top: 4px;
}

/* 로그인 폼 */
.login-box {
    background: #111827;
    border: 1px solid #1f2937;
    border-radius: 8px;
    padding: 12px;
}

/* expander 스타일 */
details {
    border: 1px solid #1f2937 !important;
    border-radius: 8px !important;
    background: #111827 !important;
}

/* 버튼 */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #10b981, #059669) !important;
    border: none !important;
    font-weight: 600 !important;
}
.stButton > button[kind="secondary"] {
    background: #374151 !important;
    border: 1px solid #4b5563 !important;
}

/* divider */
hr { border-color: #1f2937 !important; }

/* 탭 */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: #111827;
    border-radius: 8px;
    padding: 4px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 6px;
    padding: 8px 16px;
}
</style>
""", unsafe_allow_html=True)


# ── 헬퍼 함수 ──

def badge(text: str, variant: str = "") -> str:
    cls = f"badge badge-{variant}" if variant else "badge"
    return f'<span class="{cls}">{text}</span>'


def section_header(icon: str, text: str):
    st.markdown(f'<div class="section-header"><span class="icon">{icon}</span>{text}</div>', unsafe_allow_html=True)


def detail_row(label: str, value) -> str:
    return f'<div class="detail-row"><span class="detail-label">{label}</span><span class="detail-value">{value}</span></div>'


def cycle_card(value, label: str) -> str:
    return f'<div class="cycle-card"><div class="cycle-value">{value}</div><div class="cycle-label">{label}</div></div>'


# ── 관리자 비밀번호 ──

try:
    ADMIN_PASSWORD = st.secrets.get("admin_password", "fab-admin")
except Exception:
    ADMIN_PASSWORD = "fab-admin"


# ── 인증 ──

if "role" not in st.session_state:
    st.session_state.role = "viewer"


def _is_admin() -> bool:
    return st.session_state.get("role") == "admin"


# ── 사이드바 ──

st.sidebar.title("FAB-SENTINEL")
st.sidebar.caption("반도체 공정 AI 이상감지")

if _is_admin():
    st.sidebar.markdown(f'{badge("ADMIN", "done")}', unsafe_allow_html=True)
    if st.sidebar.button("로그아웃", use_container_width=True):
        st.session_state.role = "viewer"
        st.rerun()
else:
    with st.sidebar.expander("관리자 로그인"):
        pw = st.text_input("비밀번호", type="password", key="admin_pw")
        if st.button("로그인", use_container_width=True):
            if pw == ADMIN_PASSWORD:
                st.session_state.role = "admin"
                st.rerun()
            else:
                st.error("비밀번호 틀림")

st.sidebar.divider()

page = st.sidebar.radio(
    "페이지",
    ["대시보드", "이상 목록", "규칙 관리", "처리 로그"],
)

st.sidebar.divider()

try:
    health = api.get_health()
    if health.get("status") == "ok":
        st.sidebar.markdown(f"🟢 시스템 정상")
    else:
        st.sidebar.markdown(f"🟡 {health.get('status')}")
except Exception:
    st.sidebar.markdown("🔴 API 연결 실패")


# ══════════════════════════════════════════
# 페이지 1: 대시보드
# ══════════════════════════════════════════

if page == "대시보드":
    st_autorefresh(interval=10_000, key="dash_refresh")

    try:
        overview = api.get_overview()
        stats = api.get_stats()
    except Exception as e:
        st.error(f"API 조회 실패: {e}")
        st.stop()

    summary = overview.get("anomaly_summary", {})
    last_cycle = overview.get("last_cycle")

    # KPI
    section_header("📊", "실시간 현황")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown('<div class="kpi-danger">', unsafe_allow_html=True)
        st.metric("활성 위험", summary.get("active_critical", 0))
        st.markdown('</div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="kpi-warning">', unsafe_allow_html=True)
        st.metric("활성 경고", summary.get("active_warning", 0))
        st.markdown('</div>', unsafe_allow_html=True)
    with c3:
        st.markdown('<div class="kpi-info">', unsafe_allow_html=True)
        st.metric("24h 이상", summary.get("total", 0))
        st.markdown('</div>', unsafe_allow_html=True)
    with c4:
        st.markdown('<div class="kpi-success">', unsafe_allow_html=True)
        st.metric("활성 규칙", stats.get("active_rules", 0))
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col_left, col_right = st.columns(2)

    with col_left:
        section_header("📈", "상태 분포 (24h)")
        status_data = {
            "detected": summary.get("detected", 0),
            "acknowledged": summary.get("acknowledged", 0),
            "investigating": summary.get("investigating", 0),
        }
        labels = list(status_data.keys())
        values = list(status_data.values())
        colors = ["#ef4444", "#f59e0b", "#3b82f6"]
        fig = go.Figure(go.Bar(
            x=values, y=labels, orientation="h",
            marker_color=colors,
            text=values, textposition="auto",
            textfont=dict(size=14, color="white"),
        ))
        fig.update_layout(
            height=180, margin=dict(l=0, r=20, t=0, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#9ca3af",
            xaxis=dict(showgrid=False, showticklabels=False),
            yaxis=dict(showgrid=False, tickfont=dict(size=13)),
            bargap=0.35,
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        section_header("🔄", "마지막 감지 사이클")
        if last_cycle:
            lc1, lc2, lc3 = st.columns(3)
            lc1.markdown(cycle_card(last_cycle.get("rules_evaluated", 0), "규칙 평가"), unsafe_allow_html=True)
            lc2.markdown(cycle_card(last_cycle.get("anomalies_found", 0), "이상 감지"), unsafe_allow_html=True)
            dur = last_cycle.get("duration_ms")
            lc3.markdown(cycle_card(f"{dur}ms" if dur else "-", "소요시간"), unsafe_allow_html=True)
            st.caption(f"시작: {last_cycle.get('started_at', '')}")
        else:
            st.info("아직 감지 사이클이 실행되지 않았습니다.")

    st.markdown("<br>", unsafe_allow_html=True)

    if _is_admin():
        if st.button("⚡ 수동 감지 실행", type="primary", use_container_width=True):
            with st.spinner("감지 중..."):
                try:
                    result = api.trigger_detection()
                    st.success(
                        f"완료: {result.get('rules_evaluated', 0)}개 규칙, "
                        f"{result.get('anomalies_found', 0)}개 이상 "
                        f"({result.get('duration_ms', 0)}ms)"
                    )
                except Exception as e:
                    st.error(f"감지 실패: {e}")
    else:
        st.info("수동 감지는 관리자만 가능합니다.")


# ══════════════════════════════════════════
# 페이지 2: 이상 목록
# ══════════════════════════════════════════

elif page == "이상 목록":
    st_autorefresh(interval=10_000, key="anomaly_refresh")
    section_header("🚨", "이상 목록")

    status_filter = st.radio(
        "상태 필터",
        ["전체", "detected", "acknowledged", "investigating", "resolved", "false_positive"],
        horizontal=True,
    )

    try:
        if status_filter == "전체":
            anomalies = api.get_anomalies(limit=200)
        else:
            anomalies = api.get_anomalies(status=status_filter, limit=200)
    except Exception as e:
        st.error(f"API 조회 실패: {e}")
        st.stop()

    if not anomalies:
        st.info("해당 상태의 이상이 없습니다.")
        st.stop()

    col_list, col_detail = st.columns([1, 1])

    with col_list:
        st.markdown(f"**{len(anomalies)}건**")
        df = pd.DataFrame([
            {
                "ID": a.get("anomaly_id"),
                "심각도": a.get("severity", ""),
                "제목": (a.get("title") or "")[:50],
                "카테고리": a.get("category", ""),
                "상태": a.get("status", ""),
                "RCA": a.get("rca_status", ""),
                "감지시각": str(a.get("detected_at", ""))[:19],
            }
            for a in anomalies
        ])

        selection = st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            selection_mode="single-row",
            on_select="rerun",
            key="anomaly_table",
        )

    with col_detail:
        selected_rows = selection.selection.rows if selection and selection.selection else []
        if not selected_rows:
            st.markdown('<div class="detail-card" style="text-align:center;color:#6b7280;padding:40px;">좌측 목록에서 이상을 선택하세요</div>', unsafe_allow_html=True)
        else:
            idx = selected_rows[0]
            a = anomalies[idx]
            sev = a.get("severity", "warning")
            status_val = a.get("status", "detected")
            rca_val = a.get("rca_status", "pending")

            # 상세 카드
            badges_html = f'{badge(sev.upper(), sev)} {badge(status_val, status_val)} {badge("RCA:" + rca_val, rca_val)}'
            detail_html = f"""
            <div class="detail-card">
                <div style="margin-bottom:12px">{badges_html}</div>
                <h3 style="color:#f3f4f6;margin:8px 0">{a.get('title', '')}</h3>
                {detail_row('이상 ID', a.get('anomaly_id', ''))}
                {detail_row('카테고리', a.get('category', ''))}
                {detail_row('영향 대상', a.get('affected_entity', '') or '-')}
                {detail_row('감지 시각', a.get('detected_at', ''))}
                {detail_row('측정값', a.get('measured_value', 'N/A'))}
                {detail_row('임계치', a.get('threshold_value', 'N/A'))}
            </div>
            """
            st.markdown(detail_html, unsafe_allow_html=True)

            desc = a.get("description", "")
            if desc:
                st.markdown(f"**설명**: {desc}")

            analysis = a.get("llm_analysis")
            if analysis:
                section_header("🤖", "AI 분석")
                st.markdown(analysis)

            suggestion = a.get("llm_suggestion")
            if suggestion:
                section_header("💡", "AI 제안")
                try:
                    actions = json.loads(suggestion) if isinstance(suggestion, str) else suggestion
                    if isinstance(actions, list):
                        for i, act in enumerate(actions, 1):
                            st.markdown(f"{i}. {act}")
                    else:
                        st.markdown(str(suggestion))
                except (json.JSONDecodeError, TypeError):
                    st.markdown(str(suggestion))

            # 상태 전이 (관리자만)
            if _is_admin():
                st.markdown("<br>", unsafe_allow_html=True)
                current = a.get("status", "detected")
                anomaly_id = a["anomaly_id"]

                btn_cols = st.columns(4)
                if current == "detected":
                    if btn_cols[0].button("✅ 확인", key=f"ack_{anomaly_id}", use_container_width=True):
                        try:
                            api.update_anomaly_status(anomaly_id, "acknowledged")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
                if current in ("detected", "acknowledged"):
                    if btn_cols[1].button("🔍 조사 중", key=f"inv_{anomaly_id}", use_container_width=True):
                        try:
                            api.update_anomaly_status(anomaly_id, "investigating")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
                if current in ("acknowledged", "investigating"):
                    if btn_cols[2].button("✔ 해결", key=f"res_{anomaly_id}", use_container_width=True):
                        try:
                            api.update_anomaly_status(anomaly_id, "resolved", resolved_by="dashboard")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
                    if btn_cols[3].button("❌ 오탐", key=f"fp_{anomaly_id}", use_container_width=True):
                        try:
                            api.update_anomaly_status(anomaly_id, "false_positive", resolved_by="dashboard")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))


# ══════════════════════════════════════════
# 페이지 3: 규칙 관리
# ══════════════════════════════════════════

elif page == "규칙 관리":
    section_header("⚙️", "규칙 관리")

    try:
        rules = api.get_rules()
    except Exception as e:
        st.error(f"API 조회 실패: {e}")
        st.stop()

    # ── 규칙 추가 (관리자) ──
    if _is_admin():
        with st.expander("➕ 새 규칙 추가", expanded=False):
            add_tab1, add_tab2, add_tab3 = st.tabs(["💬 자연어로 만들기", "🧭 가이드 빌더", "📝 직접 입력"])

            # ── 탭1: 자연어 ──
            with add_tab1:
                st.markdown("""
                <div class="detail-card">
                    <p style="color:#9ca3af;margin:0">이상 조건을 자연어로 설명하면 AI가 감지 규칙을 자동 생성합니다.</p>
                </div>
                """, unsafe_allow_html=True)

                st.markdown("**💡 이렇게 설명해보세요:**")
                examples = {
                    "상대적 비교 (AI 판단)": [
                        "어떤 공정에 재공이 많이 쌓였는데, 전체 평균 대비 그 공정만 유독 높으면 이상이야. 전체적으로 높은 건 괜찮아.",
                        "특정 라인의 반송 시간이 다른 라인보다 2배 이상 느리면 이상이야",
                        "설비 가동률이 다른 설비 평균보다 30% 이상 떨어지는 설비가 있으면 알려줘",
                    ],
                    "단순 임계값": [
                        "컨베이어 부하율이 85%를 넘으면 경고, 95%를 넘으면 위험",
                        "AGV 에러 상태가 전체의 20% 이상이면 경고",
                    ],
                    "복합 조건 (AI 판단)": [
                        "설비가 DOWN인데 알람 이력이 없으면 비정상이야. 알람이 있으면 대응 중이니까 괜찮아.",
                        "대기 큐에서 평균 대기시간이 15분을 넘으면 경고, 어떤 공정이 문제인지와 원인도 AI가 분석해줘",
                    ],
                }
                for group, exs in examples.items():
                    st.markdown(f"**{group}**")
                    for ex in exs:
                        st.caption(f"  - _{ex}_")

                nl_desc = st.text_area(
                    "이상 조건 설명",
                    height=120,
                    placeholder="예: 어떤 공정에 재공이 많이 쌓였는데, 전체 평균 대비 그 공정만 유독 높으면 이상이야. 전체적으로 높은 건 괜찮아.",
                    key="nl_desc",
                )

                if st.button("🤖 AI로 규칙 생성", type="primary", use_container_width=True, key="nl_gen"):
                    if not nl_desc:
                        st.error("이상 조건을 설명해주세요.")
                    else:
                        with st.spinner("AI가 규칙을 생성하고 있습니다..."):
                            try:
                                gen = api.generate_rule(nl_desc)
                                st.session_state["generated_rule"] = gen
                            except Exception as e:
                                st.error(f"생성 실패: {e}")

                # 생성 결과 표시 + 확인/수정/등록
                if "generated_rule" in st.session_state:
                    gen = st.session_state["generated_rule"]
                    explanation = gen.pop("explanation", "")

                    if explanation:
                        st.info(f"**AI 설명**: {explanation}")

                    st.markdown("**생성된 규칙 (수정 가능):**")

                    with st.form("nl_confirm_form"):
                        g_name = st.text_input("규칙명", value=gen.get("rule_name", ""))
                        gc1, gc2 = st.columns(2)
                        categories = ["logistics", "wip", "equipment"]
                        g_cat_idx = categories.index(gen.get("category", "logistics")) if gen.get("category") in categories else 0
                        g_category = gc1.selectbox("카테고리", categories, index=g_cat_idx, key="g_cat")
                        g_subcategory = gc2.text_input("서브카테고리", value=gen.get("subcategory") or "")
                        check_types = ["threshold", "delta", "absence", "llm"]
                        g_ct_idx = check_types.index(gen.get("check_type", "threshold")) if gen.get("check_type") in check_types else 0
                        g_check_type = st.selectbox("검사 유형", check_types, index=g_ct_idx, key="g_ct")
                        g_query = st.text_area("SQL 쿼리", value=gen.get("query_template", ""), height=120, key="g_query")
                        gtc1, gtc2, gtc3 = st.columns(3)
                        ops = [">", "<", ">=", "<=", "=", "!="]
                        g_op_idx = ops.index(gen.get("threshold_op", ">")) if gen.get("threshold_op") in ops else 0
                        g_op = gtc1.selectbox("연산자", ops, index=g_op_idx, key="g_op")
                        g_warning = gtc2.number_input("경고", value=float(gen.get("warning_value") or 0), format="%.2f", key="g_warn")
                        g_critical = gtc3.number_input("위험", value=float(gen.get("critical_value") or 0), format="%.2f", key="g_crit")
                        g_llm = st.checkbox("LLM 분석 활성화", value=bool(gen.get("llm_enabled")), key="g_llm")
                        g_prompt = st.text_area("LLM 프롬프트", value=gen.get("llm_prompt") or "", height=80, key="g_prompt")

                        gc_submit, gc_cancel = st.columns(2)
                        confirmed = gc_submit.form_submit_button("✅ 이 규칙 등록", type="primary")
                        cancelled = gc_cancel.form_submit_button("❌ 취소")

                        if confirmed:
                            data = {
                                "rule_name": g_name,
                                "category": g_category,
                                "subcategory": g_subcategory or None,
                                "check_type": g_check_type,
                                "query_template": g_query,
                                "threshold_op": g_op,
                                "warning_value": g_warning,
                                "critical_value": g_critical,
                                "eval_interval": 300,
                                "llm_enabled": 1 if g_llm else 0,
                                "llm_prompt": g_prompt if g_llm else None,
                                "enabled": 1,
                            }
                            try:
                                result = api.create_rule(data)
                                st.success(f"규칙 등록 완료! (ID: {result.get('rule_id', '?')})")
                                del st.session_state["generated_rule"]
                                st.rerun()
                            except Exception as e:
                                st.error(f"등록 실패: {e}")
                        if cancelled:
                            del st.session_state["generated_rule"]
                            st.rerun()

            # ── 탭2: 가이드 빌더 ──
            with add_tab2:
                st.markdown("""
                <div class="detail-card">
                    <p style="color:#9ca3af;margin:0">테이블과 컬럼을 선택하면 SQL을 자동 생성합니다. SQL 몰라도 OK!</p>
                </div>
                """, unsafe_allow_html=True)

                try:
                    tables = api.get_tables()
                except Exception:
                    tables = {}

                with st.form("guide_form"):
                    guide_name = st.text_input("규칙명 *", key="guide_name")

                    # 테이블 선택
                    table_options = {k: f"{v['label']} ({k})" for k, v in tables.items()}
                    selected_table = st.selectbox(
                        "MES 테이블 *",
                        options=list(table_options.keys()),
                        format_func=lambda x: table_options.get(x, x),
                        key="guide_table",
                    )

                    # 컬럼 표시
                    if selected_table and selected_table in tables:
                        cols = tables[selected_table]["columns"]
                        st.caption(f"컬럼: {', '.join(cols)}")

                        gc1, gc2 = st.columns(2)
                        measure_col = gc1.selectbox("측정 컬럼 (숫자) *", cols, key="guide_measure")
                        group_col = gc2.selectbox("그룹 컬럼 (선택)", ["없음"] + cols, key="guide_group")

                        # 조건
                        gc3, gc4, gc5 = st.columns(3)
                        guide_op = gc3.selectbox("조건", [">", "<", ">=", "<="], key="guide_op")
                        guide_warn = gc4.number_input("경고 임계치", value=0.0, format="%.2f", key="guide_warn")
                        guide_crit = gc5.number_input("위험 임계치", value=0.0, format="%.2f", key="guide_crit")

                        # 집계
                        agg = st.selectbox("집계 함수", ["없음 (원본값)", "AVG", "MAX", "MIN", "SUM", "COUNT"], key="guide_agg")

                        # WHERE 조건 (선택)
                        where_clause = st.text_input("WHERE 조건 (선택)", placeholder="예: line_id = 'LINE01'", key="guide_where")

                        # 카테고리
                        guide_category = st.selectbox("카테고리", ["logistics", "wip", "equipment"], key="guide_cat")

                        # 자연어 판단 추가
                        guide_nl = st.text_area(
                            "AI 판단 조건 (선택)",
                            placeholder="예: 이 값이 높을 때 최근 1시간 내 장비 이력도 같이 봐서 실제 이상인지 판단해줘",
                            height=60,
                            key="guide_nl",
                        )
                    else:
                        measure_col = ""
                        group_col = "없음"
                        guide_op = ">"
                        guide_warn = 0.0
                        guide_crit = 0.0
                        agg = "없음 (원본값)"
                        where_clause = ""
                        guide_category = "logistics"
                        guide_nl = ""

                    guide_submit = st.form_submit_button("🔨 규칙 생성", type="primary")

                    if guide_submit and guide_name and selected_table and measure_col:
                        # SQL 자동 생성
                        if agg and agg != "없음 (원본값)":
                            select_expr = f"{agg}({measure_col})"
                        else:
                            select_expr = measure_col

                        group_by = ""
                        select_extra = ""
                        if group_col and group_col != "없음":
                            select_extra = f", {group_col}"
                            group_by = f"\nGROUP BY {group_col}"

                        where = ""
                        if where_clause:
                            where = f"\nWHERE {where_clause}"

                        query = f"SELECT {select_expr} AS value{select_extra}\nFROM {selected_table}{where}{group_by}\nORDER BY value DESC"

                        use_llm = bool(guide_nl and guide_nl.strip())
                        data = {
                            "rule_name": guide_name,
                            "category": guide_category,
                            "subcategory": selected_table.replace("mes_", ""),
                            "check_type": "llm" if use_llm else "threshold",
                            "query_template": query,
                            "threshold_op": guide_op,
                            "warning_value": guide_warn,
                            "critical_value": guide_crit,
                            "eval_interval": 300,
                            "llm_enabled": 1 if use_llm else 0,
                            "llm_prompt": guide_nl if use_llm else None,
                            "enabled": 1,
                        }
                        try:
                            result = api.create_rule(data)
                            st.success(f"규칙 생성 완료! (ID: {result.get('rule_id', '?')})")
                            st.caption(f"생성된 SQL: `{query}`")
                            st.rerun()
                        except Exception as e:
                            st.error(f"생성 실패: {e}")

            # ── 탭3: 직접 입력 ──
            with add_tab3:
                with st.form("add_rule_form"):
                    new_name = st.text_input("규칙명 *")
                    fc1, fc2 = st.columns(2)
                    new_category = fc1.selectbox("카테고리 *", ["logistics", "wip", "equipment"], key="d_cat")
                    new_subcategory = fc2.text_input("서브카테고리", key="d_sub")
                    new_check_type = st.selectbox("검사 유형", ["threshold", "delta", "absence", "llm"], key="d_ct")
                    new_query = st.text_area("SQL 쿼리 *", height=120, placeholder="SELECT ... FROM ...", key="d_query")
                    tc1, tc2, tc3 = st.columns(3)
                    new_op = tc1.selectbox("연산자", [">", "<", ">=", "<=", "=", "!="], key="d_op")
                    new_warning = tc2.number_input("경고 임계치", value=0.0, format="%.2f", key="d_warn")
                    new_critical = tc3.number_input("위험 임계치", value=0.0, format="%.2f", key="d_crit")
                    ec1, ec2 = st.columns(2)
                    new_interval = ec1.number_input("평가 간격(초)", value=300, min_value=10, key="d_int")
                    new_llm = ec2.checkbox("LLM 분석 활성화", key="d_llm")
                    new_prompt = st.text_area("LLM 프롬프트", height=80, key="d_prompt")

                    submitted = st.form_submit_button("규칙 추가", type="primary")
                    if submitted:
                        if not new_name or not new_query:
                            st.error("규칙명과 SQL 쿼리는 필수입니다.")
                        else:
                            data = {
                                "rule_name": new_name,
                                "category": new_category,
                                "subcategory": new_subcategory or None,
                                "check_type": new_check_type,
                                "query_template": new_query,
                                "threshold_op": new_op,
                                "warning_value": new_warning,
                                "critical_value": new_critical,
                                "eval_interval": new_interval,
                                "llm_enabled": 1 if new_llm else 0,
                                "llm_prompt": new_prompt if new_llm else None,
                                "enabled": 1,
                            }
                            try:
                                result = api.create_rule(data)
                                st.success(f"규칙 추가 완료 (ID: {result.get('rule_id', '?')})")
                                st.rerun()
                            except Exception as e:
                                st.error(f"추가 실패: {e}")

    # ── 규칙 목록 + 상세 ──

    if not rules:
        st.info("등록된 규칙이 없습니다.")
        st.stop()

    col_list, col_detail = st.columns([1, 1])

    with col_list:
        st.markdown(f"**{len(rules)}개 규칙**")
        df = pd.DataFrame([
            {
                "ID": r.get("rule_id"),
                "이름": (r.get("rule_name") or "")[:40],
                "카테고리": r.get("category", ""),
                "유형": r.get("check_type", ""),
                "LLM": "Y" if r.get("llm_enabled") else "N",
            }
            for r in rules
        ])

        selection = st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            selection_mode="single-row",
            on_select="rerun",
            key="rule_table",
        )

    with col_detail:
        selected_rows = selection.selection.rows if selection and selection.selection else []
        if not selected_rows:
            st.markdown('<div class="detail-card" style="text-align:center;color:#6b7280;padding:40px;">좌측 목록에서 규칙을 선택하세요</div>', unsafe_allow_html=True)
        else:
            idx = selected_rows[0]
            r = rules[idx]
            rule_id = r["rule_id"]

            if _is_admin():
                with st.form(f"edit_rule_{rule_id}"):
                    ed_name = st.text_input("규칙명", value=r.get("rule_name", ""))
                    ec1, ec2 = st.columns(2)
                    categories = ["logistics", "wip", "equipment"]
                    cat_idx = categories.index(r.get("category", "logistics")) if r.get("category") in categories else 0
                    ed_category = ec1.selectbox("카테고리", categories, index=cat_idx, key=f"ec_{rule_id}")
                    ed_subcategory = ec2.text_input("서브카테고리", value=r.get("subcategory") or "")
                    check_types = ["threshold", "delta", "absence", "llm"]
                    ct_idx = check_types.index(r.get("check_type", "threshold")) if r.get("check_type") in check_types else 0
                    ed_check_type = st.selectbox("검사 유형", check_types, index=ct_idx, key=f"ct_{rule_id}")
                    ed_query = st.text_area("SQL 쿼리", value=r.get("query_template", ""), height=120)
                    tc1, tc2, tc3 = st.columns(3)
                    ops = [">", "<", ">=", "<=", "=", "!="]
                    op_idx = ops.index(r.get("threshold_op", ">")) if r.get("threshold_op") in ops else 0
                    ed_op = tc1.selectbox("연산자", ops, index=op_idx, key=f"op_{rule_id}")
                    ed_warning = tc2.number_input("경고", value=float(r.get("warning_value") or 0), format="%.2f", key=f"w_{rule_id}")
                    ed_critical = tc3.number_input("위험", value=float(r.get("critical_value") or 0), format="%.2f", key=f"c_{rule_id}")
                    ec3, ec4 = st.columns(2)
                    ed_interval = ec3.number_input("평가 간격(초)", value=int(r.get("eval_interval") or 300), min_value=10, key=f"ei_{rule_id}")
                    ed_llm = ec4.checkbox("LLM 활성화", value=bool(r.get("llm_enabled")), key=f"llm_{rule_id}")
                    ed_prompt = st.text_area("LLM 프롬프트", value=r.get("llm_prompt") or "", height=80, key=f"pr_{rule_id}")

                    fc1, fc2 = st.columns(2)
                    save = fc1.form_submit_button("💾 저장", type="primary")
                    delete = fc2.form_submit_button("🗑 삭제", type="secondary")

                    if save:
                        update_data = {
                            "rule_name": ed_name,
                            "category": ed_category,
                            "subcategory": ed_subcategory or None,
                            "check_type": ed_check_type,
                            "query_template": ed_query,
                            "threshold_op": ed_op,
                            "warning_value": ed_warning,
                            "critical_value": ed_critical,
                            "eval_interval": ed_interval,
                            "llm_enabled": 1 if ed_llm else 0,
                            "llm_prompt": ed_prompt if ed_llm else None,
                        }
                        try:
                            api.update_rule(rule_id, update_data)
                            st.success("저장 완료")
                            st.rerun()
                        except Exception as e:
                            st.error(f"저장 실패: {e}")

                    if delete:
                        try:
                            api.delete_rule(rule_id)
                            st.success("삭제 완료")
                            st.rerun()
                        except Exception as e:
                            st.error(f"삭제 실패: {e}")

                if st.button("🧪 규칙 테스트", key=f"test_{rule_id}", use_container_width=True):
                    with st.spinner("테스트 중..."):
                        try:
                            result = api.test_rule(rule_id)
                            st.json(result)
                        except Exception as e:
                            st.error(f"테스트 실패: {e}")

            else:
                # 열람자
                badges_html = f'{badge(r.get("category", ""), "info")} {badge(r.get("check_type", ""), "pending")}'
                detail_html = f"""
                <div class="detail-card">
                    <div style="margin-bottom:12px">{badges_html}</div>
                    <h3 style="color:#f3f4f6;margin:8px 0">{r.get('rule_name', '')}</h3>
                    {detail_row('서브카테고리', r.get('subcategory') or '-')}
                    {detail_row('연산자', r.get('threshold_op', '>'))}
                    {detail_row('경고 임계치', r.get('warning_value', 'N/A'))}
                    {detail_row('위험 임계치', r.get('critical_value', 'N/A'))}
                    {detail_row('평가 간격', f"{r.get('eval_interval', 300)}초")}
                    {detail_row('LLM', '활성화' if r.get('llm_enabled') else '비활성화')}
                </div>
                """
                st.markdown(detail_html, unsafe_allow_html=True)

                query = r.get("query_template", "")
                if query:
                    st.code(query, language="sql")


# ══════════════════════════════════════════
# 페이지 4: 처리 로그
# ══════════════════════════════════════════

elif page == "처리 로그":
    st_autorefresh(interval=10_000, key="log_refresh")
    section_header("📋", "처리 로그")

    tab1, tab2, tab3 = st.tabs(["🔄 감지 사이클", "🤖 RCA 이력", "📨 알림 이력"])

    with tab1:
        try:
            overview = api.get_overview()
            last_cycle = overview.get("last_cycle")
            if last_cycle:
                st.dataframe(
                    pd.DataFrame([last_cycle]),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("감지 사이클 이력이 없습니다.")
        except Exception as e:
            st.error(f"조회 실패: {e}")

    with tab2:
        try:
            anomalies = api.get_anomalies(limit=50)
            for rca_status in ["processing", "done", "failed", "pending"]:
                filtered = [a for a in anomalies if a.get("rca_status") == rca_status]
                if filtered:
                    st.markdown(f'{badge(rca_status.upper() + f" ({len(filtered)})", rca_status)}', unsafe_allow_html=True)
                    df = pd.DataFrame([
                        {
                            "ID": a.get("anomaly_id"),
                            "제목": (a.get("title") or "")[:50],
                            "심각도": a.get("severity", ""),
                            "감지시각": str(a.get("detected_at", ""))[:19],
                        }
                        for a in filtered
                    ])
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    st.markdown("<br>", unsafe_allow_html=True)
        except Exception as e:
            st.error(f"조회 실패: {e}")

    with tab3:
        try:
            alerts = api.get_alert_history(limit=50)
            if alerts:
                df = pd.DataFrame([
                    {
                        "ID": a.get("alert_id"),
                        "이상 ID": a.get("anomaly_id"),
                        "채널": a.get("channel", ""),
                        "발송시각": str(a.get("sent_at", ""))[:19],
                        "성공": "Y" if a.get("delivered") else "N",
                    }
                    for a in alerts
                ])
                st.dataframe(df, use_container_width=True, hide_index=True)

                st.markdown("---")
                alert_id = st.selectbox(
                    "알림 메시지 보기",
                    [a.get("alert_id") for a in alerts],
                    format_func=lambda x: f"Alert #{x}",
                )
                if alert_id:
                    sel = next((a for a in alerts if a.get("alert_id") == alert_id), None)
                    if sel and sel.get("message"):
                        st.markdown(f'<div class="detail-card">{sel["message"]}</div>', unsafe_allow_html=True)
            else:
                st.info("알림 이력이 없습니다.")
        except Exception as e:
            st.error(f"조회 실패: {e}")
