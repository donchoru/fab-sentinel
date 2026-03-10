"""FAB 이상감지 대시보드."""

from __future__ import annotations

import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

import api_client as api

st.set_page_config(
    page_title="FAB 이상감지",
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
    st.session_state.role = "admin"


def _is_admin() -> bool:
    return st.session_state.get("role") == "admin"


# ── 사이드바 ──

st.sidebar.title("FAB 이상감지")
st.sidebar.caption("반도체 공정 AI 이상감지 시스템")

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
    ["대시보드", "이상 목록", "규칙 관리", "감지 로그"],
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

            # 상세 카드
            badges_html = f'{badge(sev.upper(), sev)} {badge(status_val, status_val)}'
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

    # ── 도구 카탈로그 로드 ──
    try:
        tool_catalog = api.get_tool_catalog()
    except Exception:
        tool_catalog = {}

    def _tool_options():
        return {k: f"{v['label']} ({k})" for k, v in tool_catalog.items()}

    # ── 규칙 추가 (관리자) ──
    if _is_admin():
        with st.expander("➕ 새 규칙 추가", expanded=False):
            add_tab1, add_tab2 = st.tabs(["📊 임계치 감시", "🤖 AI 판단"])

            # ── 탭1: 임계치 감시 ──
            with add_tab1:
                st.markdown("""
                <div class="detail-card">
                    <p style="color:#9ca3af;margin:0">도구를 연결하고, 감시할 컬럼과 임계치를 설정합니다.</p>
                </div>
                """, unsafe_allow_html=True)

                with st.form("threshold_form"):
                    th_name = st.text_input("규칙명 *", placeholder="예: 컨베이어 부하율 과부하")

                    # 도구 선택
                    tool_opts = _tool_options()
                    th_tool = st.selectbox(
                        "감시 도구 *",
                        options=list(tool_opts.keys()),
                        format_func=lambda x: tool_opts.get(x, x),
                        key="th_tool",
                    )

                    # 선택된 도구의 파라미터 & 컬럼
                    tool_info = tool_catalog.get(th_tool, {})
                    if tool_info:
                        st.caption(f"📋 {tool_info.get('description', '')}")

                        # 도구 파라미터 입력
                        tool_params = tool_info.get("params", [])
                        th_args = {}
                        if tool_params:
                            param_cols = st.columns(len(tool_params))
                            for i, p in enumerate(tool_params):
                                with param_cols[i]:
                                    val = st.text_input(
                                        f"{p['label']} {'*' if p.get('required') else '(선택)'}",
                                        key=f"th_p_{p['name']}",
                                    )
                                    if val:
                                        if p.get("type") == "integer":
                                            try:
                                                th_args[p["name"]] = int(val)
                                            except ValueError:
                                                th_args[p["name"]] = val
                                        else:
                                            th_args[p["name"]] = val

                        # 컬럼 선택
                        columns = tool_info.get("columns", [])
                        col_options = [c["name"] for c in columns]
                        col_labels = {c["name"]: c["label"] for c in columns}
                        th_column = st.selectbox(
                            "감시 컬럼 *",
                            options=col_options,
                            format_func=lambda x: f"{col_labels.get(x, x)} ({x})",
                            key="th_col",
                        )

                    # 임계치
                    tc1, tc2, tc3 = st.columns(3)
                    th_op = tc1.selectbox("조건", [">", "<", ">=", "<="], key="th_op")
                    th_warn = tc2.number_input("경고 임계치 *", value=0.0, format="%.2f", key="th_warn")
                    th_crit = tc3.number_input("위험 임계치 *", value=0.0, format="%.2f", key="th_crit")

                    th_submit = st.form_submit_button("✅ 규칙 등록", type="primary")
                    if th_submit:
                        if not th_name or not th_tool:
                            st.error("규칙명과 도구는 필수입니다.")
                        else:
                            import json as _json
                            data = {
                                "rule_name": th_name,
                                "category": tool_info.get("category", "logistics"),
                                "subcategory": th_tool.replace("get_", ""),
                                "source_type": "tool",
                                "tool_name": th_tool,
                                "tool_args": _json.dumps(th_args) if th_args else None,
                                "tool_column": th_column if tool_info else None,
                                "check_type": "threshold",
                                "threshold_op": th_op,
                                "warning_value": th_warn,
                                "critical_value": th_crit,
                                "eval_interval": 300,
                                "llm_enabled": 0,
                                "enabled": 1,
                            }
                            try:
                                result = api.create_rule(data)
                                st.success(f"규칙 등록 완료! (ID: {result.get('rule_id', '?')})")
                                st.rerun()
                            except Exception as e:
                                st.error(f"등록 실패: {e}")

            # ── 탭2: AI 판단 ──
            with add_tab2:
                st.markdown("""
                <div class="detail-card">
                    <p style="color:#9ca3af;margin:0">도구를 연결하고, 자연어로 이상 조건을 설명하면 AI가 판단합니다.</p>
                </div>
                """, unsafe_allow_html=True)

                st.markdown("**💡 이렇게 설명해보세요:**")
                st.caption("- _특정 공정만 유독 WIP가 높으면 이상. 전체적으로 높은 건 정상._")
                st.caption("- _ERROR 상태 AGV가 전체의 30%를 넘으면 위험_")
                st.caption("- _설비가 DOWN인데 알람이 없으면 비정상. 알람이 있으면 대응 중._")

                with st.form("llm_form"):
                    ai_name = st.text_input("규칙명 *", placeholder="예: 특정 공정만 WIP 높으면 이상")

                    # 도구 선택
                    ai_tool = st.selectbox(
                        "데이터 도구 *",
                        options=list(tool_opts.keys()),
                        format_func=lambda x: tool_opts.get(x, x),
                        key="ai_tool",
                    )

                    ai_tool_info = tool_catalog.get(ai_tool, {})
                    if ai_tool_info:
                        st.caption(f"📋 {ai_tool_info.get('description', '')}")

                        # 도구 파라미터
                        ai_params = ai_tool_info.get("params", [])
                        ai_args = {}
                        if ai_params:
                            param_cols = st.columns(len(ai_params))
                            for i, p in enumerate(ai_params):
                                with param_cols[i]:
                                    val = st.text_input(
                                        f"{p['label']} {'*' if p.get('required') else '(선택)'}",
                                        key=f"ai_p_{p['name']}",
                                    )
                                    if val:
                                        if p.get("type") == "integer":
                                            try:
                                                ai_args[p["name"]] = int(val)
                                            except ValueError:
                                                ai_args[p["name"]] = val
                                        else:
                                            ai_args[p["name"]] = val

                    # 자연어 조건
                    ai_prompt = st.text_area(
                        "이상 조건 설명 *",
                        height=120,
                        placeholder="이 데이터를 보고 이상인지 판단해줘. 예: 특정 공정만 유독 높으면 이상, 전체적으로 높은 건 정상.",
                        key="ai_prompt",
                    )

                    ai_submit = st.form_submit_button("✅ 규칙 등록", type="primary")
                    if ai_submit:
                        if not ai_name or not ai_tool or not ai_prompt:
                            st.error("규칙명, 도구, 이상 조건은 필수입니다.")
                        else:
                            import json as _json
                            data = {
                                "rule_name": ai_name,
                                "category": ai_tool_info.get("category", "logistics"),
                                "subcategory": ai_tool.replace("get_", ""),
                                "source_type": "tool",
                                "tool_name": ai_tool,
                                "tool_args": _json.dumps(ai_args) if ai_args else None,
                                "check_type": "llm",
                                "llm_enabled": 1,
                                "llm_prompt": ai_prompt,
                                "eval_interval": 300,
                                "enabled": 1,
                            }
                            try:
                                result = api.create_rule(data)
                                st.success(f"규칙 등록 완료! (ID: {result.get('rule_id', '?')})")
                                st.rerun()
                            except Exception as e:
                                st.error(f"등록 실패: {e}")

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
                "소스": "도구" if r.get("source_type") == "tool" else "SQL",
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

            is_tool = r.get("source_type") == "tool"
            src_label = "도구" if is_tool else "SQL"
            tool_label = ""
            if is_tool and r.get("tool_name") in tool_catalog:
                tool_label = tool_catalog[r["tool_name"]]["label"]

            # 상세 카드
            badges_html = (
                f'{badge(r.get("category", ""), "info")} '
                f'{badge(r.get("check_type", ""), "pending")} '
                f'{badge(src_label, "done" if is_tool else "processing")}'
            )
            detail_html = f"""
            <div class="detail-card">
                <div style="margin-bottom:12px">{badges_html}</div>
                <h3 style="color:#f3f4f6;margin:8px 0">{r.get('rule_name', '')}</h3>
                {detail_row('데이터 소스', f'🔧 {tool_label} ({r.get("tool_name", "")})' if is_tool else '📝 SQL 쿼리')}
                {detail_row('감시 컬럼', r.get('tool_column') or '-') if is_tool else ''}
                {detail_row('연산자', r.get('threshold_op', '>')) if r.get('check_type') != 'llm' else ''}
                {detail_row('경고 임계치', r.get('warning_value', '-')) if r.get('check_type') != 'llm' else ''}
                {detail_row('위험 임계치', r.get('critical_value', '-')) if r.get('check_type') != 'llm' else ''}
                {detail_row('LLM 판단', '활성화' if r.get('llm_enabled') else '비활성화')}
            </div>
            """
            st.markdown(detail_html, unsafe_allow_html=True)

            # LLM 프롬프트 표시
            if r.get("llm_prompt"):
                st.markdown(f"**AI 조건**: {r['llm_prompt']}")

            # SQL 표시 (SQL 소스인 경우)
            if not is_tool and r.get("query_template"):
                st.code(r["query_template"], language="sql")

            # 관리자: 삭제 + 테스트
            if _is_admin():
                bc1, bc2 = st.columns(2)
                if bc1.button("🧪 테스트", key=f"test_{rule_id}", use_container_width=True):
                    with st.spinner("테스트 중..."):
                        try:
                            result = api.test_rule(rule_id)
                            st.json(result)
                        except Exception as e:
                            st.error(f"테스트 실패: {e}")
                if bc2.button("🗑 삭제", key=f"del_{rule_id}", use_container_width=True):
                    try:
                        api.delete_rule(rule_id)
                        st.success("삭제 완료")
                        st.rerun()
                    except Exception as e:
                        st.error(f"삭제 실패: {e}")


# ══════════════════════════════════════════
# 페이지 4: 처리 로그
# ══════════════════════════════════════════

elif page == "감지 로그":
    st_autorefresh(interval=10_000, key="log_refresh")
    section_header("📋", "감지 로그")

    try:
        overview = api.get_overview()
        last_cycle = overview.get("last_cycle")
        if last_cycle:
            section_header("🔄", "마지막 감지 사이클")
            st.dataframe(
                pd.DataFrame([last_cycle]),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("감지 사이클 이력이 없습니다.")
    except Exception as e:
        st.error(f"조회 실패: {e}")

    st.markdown("<br>", unsafe_allow_html=True)

    # 최근 감지된 이상 목록
    section_header("📊", "최근 감지 이력")
    try:
        anomalies = api.get_anomalies(limit=50)
        if anomalies:
            for status_val in ["detected", "acknowledged", "investigating", "resolved"]:
                filtered = [a for a in anomalies if a.get("status") == status_val]
                if filtered:
                    st.markdown(f'{badge(status_val.upper() + f" ({len(filtered)})", status_val)}', unsafe_allow_html=True)
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
        else:
            st.info("감지된 이상이 없습니다.")
    except Exception as e:
        st.error(f"조회 실패: {e}")
