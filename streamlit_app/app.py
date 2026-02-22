import datetime
import json
import logging
import os
import shutil
import sys
import tempfile
import time

# Ensure project root and app directory are on sys.path regardless of cwd.
_app_dir = os.path.abspath(os.path.dirname(__file__))
_project_root = os.path.abspath(os.path.join(_app_dir, ".."))
for _p in (_project_root, _app_dir):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import streamlit as st

st.set_page_config(
    page_title="SpeakNode",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

logger = logging.getLogger("speaknode.app")

import view_components as vc  # noqa: E402
from core.pipeline import SpeakNodeEngine
from core.shared.share_manager import ShareManager
from core.db.kuzu_manager import KuzuManager
from core.config import SpeakNodeConfig, get_meeting_db_path, list_meeting_ids

_config = SpeakNodeConfig()
MEETING_DB_DIR = _config.db_base_dir
os.makedirs(MEETING_DB_DIR, exist_ok=True)

SHARED_CARDS_DIR = os.path.join(_project_root, "shared_cards")
share_mgr = ShareManager(output_dir=SHARED_CARDS_DIR)


@st.cache_resource
def get_engine() -> SpeakNodeEngine:
    logger.info("Initialising SpeakNodeEngine...")
    return SpeakNodeEngine()


def get_meeting_label(meeting_id: str) -> str:
    """Return a human-readable label from metadata.json, or the raw ID as fallback."""
    meta_path = os.path.join(MEETING_DB_DIR, meeting_id, "metadata.json")
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        title = meta.get("title", meeting_id)
        date  = meta.get("date", "")
        return f"{title} ({date})" if date else title
    except Exception:
        return meeting_id


# Initialize session state.
_defaults: dict = {
    "analysis_result": None,
    "active_meeting_id": None,
    "current_page": "📊 분석 결과",
    "_save_image_buf": None,
}
for _k, _v in _defaults.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# Apply custom CSS.
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] { background: #0f172a !important; }
    [data-testid="stSidebar"] * { color: #e2e8f0; }
    [data-testid="stSidebar"] .stRadio > label { font-size: 0.9rem; }
    .block-container { padding-top: 1.2rem; }
    .stMetric { background: #1e293b; border-radius: 8px; padding: 10px 14px; }
    </style>
    """,
    unsafe_allow_html=True,
)

vc.render_header()

# Sidebar.
current_db_path: str | None = None

with st.sidebar:
    st.markdown("---")

    # New meeting upload.
    with st.expander("🎤 새 회의 분석", expanded=True):
        uploaded_audio = st.file_uploader(
            "오디오 파일 (MP3, WAV, M4A)",
            type=["mp3", "wav", "m4a"],
            label_visibility="collapsed",
        )
        meeting_title_input = st.text_input(
            "회의 제목 (선택)",
            placeholder="예: 2026-02-21 스프린트 리뷰",
        )
        analyze_btn = st.button(
            "🚀 분석 시작",
            type="primary",
            use_container_width=True,
            disabled=(uploaded_audio is None),
        )

    st.markdown("---")

    # Meeting list.
    st.markdown("**📁 회의 목록**")
    meeting_ids = list_meeting_ids(_config)

    if meeting_ids:
        active_id = st.session_state.get("active_meeting_id")
        default_index = meeting_ids.index(active_id) if active_id in meeting_ids else 0

        selected_meeting_id = st.selectbox(
            "회의 선택",
            options=meeting_ids,
            index=default_index,
            format_func=get_meeting_label,
            label_visibility="collapsed",
        )
        if selected_meeting_id != st.session_state.get("active_meeting_id"):
            st.session_state["active_meeting_id"] = selected_meeting_id
            st.session_state["analysis_result"] = None
            st.session_state["_save_image_buf"] = None
            st.rerun()

        current_db_path = get_meeting_db_path(selected_meeting_id, _config)

        if st.button("🗑️ 현재 회의 DB 초기화", use_container_width=True, type="secondary"):
            try:
                st.session_state["analysis_result"] = None
                st.session_state["active_meeting_id"] = None
                st.session_state["_save_image_buf"] = None
                if os.path.exists(current_db_path):
                    time.sleep(0.1)
                    shutil.rmtree(current_db_path)
                st.success("회의 DB가 초기화되었습니다.")
                time.sleep(0.5)
                st.rerun()
            except Exception as e:
                st.error(f"초기화 실패: {e}")
    else:
        st.info("분석된 회의가 없습니다.\n왼쪽 패널에서 오디오 파일을 업로드하세요.")

    st.markdown("---")

    # Page navigation (only after analysis is loaded).
    if st.session_state["analysis_result"]:
        _pages = ["📊 분석 결과", "🧠 지식 그래프", "💬 AI Agent"]
        _cur_page = st.session_state.get("current_page", _pages[0])
        _cur_idx = _pages.index(_cur_page) if _cur_page in _pages else 0
        page = st.radio(
            "페이지",
            options=_pages,
            index=_cur_idx,
            label_visibility="collapsed",
        )
        st.session_state["current_page"] = page

    st.markdown("---")
    st.caption(f"🤖 모델: `{_config.llm_model}`")


# Audio analysis pipeline.
if uploaded_audio and analyze_btn:
    ext = os.path.splitext(uploaded_audio.name)[1] or ".mp3"
    tmp_fd, temp_audio = tempfile.mkstemp(suffix=ext, prefix="speaknode_")
    try:
        with os.fdopen(tmp_fd, "wb") as f:
            f.write(uploaded_audio.getbuffer())
    except Exception:
        os.close(tmp_fd)
        st.error("임시 파일 저장에 실패했습니다.")
        st.stop()

    new_meeting_id = "m_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    new_db_path    = get_meeting_db_path(new_meeting_id, _config)

    with st.status("🎙️ 회의 분석 중...", expanded=True) as status_box:
        progress_bar  = st.progress(0)
        status_text   = st.empty()

        def _progress_cb(step: str, percent: int, message: str):
            progress_bar.progress(max(0, min(percent, 100)) / 100)
            status_text.markdown(f"**{message}**")

        try:
            engine = get_engine()
            result = engine.process(
                temp_audio,
                db_path=new_db_path,
                meeting_title=meeting_title_input,
                meeting_id=new_meeting_id,
                progress_callback=_progress_cb,
            )
            if result:
                st.session_state["active_meeting_id"] = new_meeting_id
                st.session_state["analysis_result"]   = result
                st.session_state["current_page"]      = "📊 분석 결과"
                st.session_state["_save_image_buf"]   = None
                current_db_path = new_db_path
                status_box.update(label="✅ 분석 완료!", state="complete", expanded=False)
            else:
                status_box.update(label="⚠️ 추출 결과 없음", state="error")
                st.warning("분석 결과가 생성되지 않았습니다.")
        except Exception as e:
            st.error(f"분석 오류: {e}")
            logger.error("Analysis error: %s", e, exc_info=True)
            status_box.update(label="❌ 분석 실패", state="error")
        finally:
            if os.path.exists(temp_audio):
                try:
                    os.remove(temp_audio)
                except OSError as ose:
                    logger.warning("Failed to remove temp file: %s", ose)

    st.rerun()

# Main content.
if not st.session_state["analysis_result"]:
    # Welcome and onboarding.
    vc.render_welcome_page()

    # Allow importing a previously exported graph image.
    restored_data = vc.render_import_card_ui(share_mgr)
    if restored_data:
        bundle_format = restored_data.get("format") if isinstance(restored_data, dict) else ""
        if bundle_format == "speaknode_graph_bundle_v1":
            restored_analysis  = restored_data.get("analysis_result", {})
            restored_graph_dump = restored_data.get("graph_dump", {})
        else:
            restored_analysis  = restored_data
            restored_graph_dump = {}

        st.session_state["analysis_result"] = restored_analysis

        new_meeting_id = "m_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        new_db_path    = get_meeting_db_path(new_meeting_id, _config)
        try:
            with KuzuManager(new_db_path, config=_config) as db_mgr:
                if restored_graph_dump:
                    db_mgr.restore_graph_dump(restored_graph_dump)
                    st.success("✅ 전체 그래프 데이터가 복원되었습니다.")
                else:
                    db_mgr.ingest_data(restored_analysis)
                    st.success("✅ 분석 데이터가 복원되었습니다.")
            st.session_state["active_meeting_id"] = new_meeting_id
            st.session_state["current_page"]      = "📊 분석 결과"
            current_db_path = new_db_path
        except Exception as e:
            st.error(f"DB 복원 오류: {e}")

        time.sleep(0.5)
        st.rerun()

else:
    result            = st.session_state["analysis_result"]
    active_meeting_id = st.session_state.get("active_meeting_id", "")
    current_page      = st.session_state.get("current_page", "📊 분석 결과")

    # Ensure `current_db_path` is set when arriving from selectbox navigation.
    if not current_db_path and active_meeting_id:
        current_db_path = get_meeting_db_path(active_meeting_id, _config)

    # Analysis results page.
    if current_page == "📊 분석 결과":
        meeting_label = get_meeting_label(active_meeting_id) if active_meeting_id else ""
        st.markdown(f"### 📊 분석 결과")
        if meeting_label:
            st.caption(f"회의: **{meeting_label}**")

        vc.display_analysis_cards(result)

    # Knowledge graph page.
    elif current_page == "🧠 지식 그래프":
        meeting_label = get_meeting_label(active_meeting_id) if active_meeting_id else ""
        st.markdown("### 🧠 지식 그래프")
        if meeting_label:
            st.caption(f"회의: **{meeting_label}**")

        if current_db_path and os.path.exists(current_db_path):
            vc.render_graph_view(current_db_path)
            st.divider()
            vc.render_graph_editor(current_db_path)
            st.divider()
            # Keep save controls inline on this page.
            vc.render_save_section(current_db_path, result)
        else:
            st.info("이 회의의 그래프 데이터가 아직 없습니다.")

    # AI agent page.
    elif current_page == "💬 AI Agent":
        st.markdown("### 💬 AI Agent")
        st.caption("회의 데이터를 기반으로 대화하세요. 이메일 작성 초안도 지원합니다.")

        history_key = f"agent_chat_history::{active_meeting_id}"
        if history_key not in st.session_state:
            st.session_state[history_key] = []
        chat_history: list[dict] = st.session_state[history_key]

        # Render existing chat messages.
        for msg in chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # Show suggested prompts when chat is empty.
        if not chat_history:
            st.markdown("**💡 예시 질문**")
            ex_cols = st.columns(3)
            examples = [
                "이번 회의에서 결정된 사항을 알려줘",
                "누가 어떤 할 일을 맡았어?",
                "회의 결과를 팀원에게 이메일로 보내줘",
            ]
            for i, ex in enumerate(examples):
                if ex_cols[i].button(ex, key=f"example_{i}", use_container_width=True):
                    st.session_state["_pending_agent_query"] = ex
                    st.rerun()

        pending_query = st.session_state.pop("_pending_agent_query", None)
        user_input    = st.chat_input("회의 데이터에 대해 질문하세요...")
        query         = pending_query or user_input

        if query and current_db_path:
            chat_history.append({"role": "user", "content": query})
            with st.chat_message("user"):
                st.markdown(query)

            with st.chat_message("assistant"):
                with st.spinner("🔍 분석 중..."):
                    try:
                        engine = get_engine()
                        agent  = engine.create_agent(db_path=current_db_path)

                        from langchain_core.messages import HumanMessage as HM, AIMessage as AM

                        lc_history = []
                        for m in chat_history[:-1]:
                            lc_history.append(
                                HM(content=m["content"]) if m["role"] == "user"
                                else AM(content=m["content"])
                            )

                        response = agent.query(query, chat_history=lc_history)
                        st.markdown(response)
                        chat_history.append({"role": "assistant", "content": response})
                    except Exception as e:
                        err_msg = f"❌ Agent 오류: {e}"
                        st.error(err_msg)
                        chat_history.append({"role": "assistant", "content": err_msg})

        if chat_history:
            if st.button("🗑️ 대화 초기화", key="clear_agent_chat"):
                st.session_state[history_key] = []
                st.rerun()
