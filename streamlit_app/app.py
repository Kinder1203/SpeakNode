import datetime
import json
import logging
import os
import shutil
import sys
import time

# Ensure project root and app directory are resolvable regardless of cwd.
_app_dir = os.path.abspath(os.path.dirname(__file__))
_project_root = os.path.abspath(os.path.join(_app_dir, ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

import streamlit as st

st.set_page_config(page_title="SpeakNode", layout="wide")

import matplotlib  # noqa: E402 — must come after set_page_config
matplotlib.use("Agg")

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
        date = meta.get("date", "")
        return f"{title} ({date})" if date else title
    except Exception:
        return meeting_id


# ── Session state initialisation ──────────────────────────────────────────────
if "analysis_result" not in st.session_state:
    st.session_state["analysis_result"] = None
if "active_meeting_id" not in st.session_state:
    st.session_state["active_meeting_id"] = None

vc.render_header()

# ── Sidebar ───────────────────────────────────────────────────────────────────
current_db_path: str | None = None

with st.sidebar:
    st.header("Workspace")
    uploaded_audio = st.file_uploader(
        "Audio file (MP3, WAV, M4A)", type=["mp3", "wav", "m4a"]
    )
    meeting_title_input = st.text_input(
        "Meeting title (optional)",
        placeholder="e.g. 2026-02-21 Sprint Review",
        help="Leave blank to auto-generate from file name.",
    )

    st.divider()
    st.subheader("Meetings")

    meeting_ids = list_meeting_ids(_config)
    if meeting_ids:
        active_id = st.session_state.get("active_meeting_id")
        default_index = (
            meeting_ids.index(active_id) if active_id in meeting_ids else 0
        )
        selected_meeting_id = st.selectbox(
            "Select meeting",
            options=meeting_ids,
            index=default_index,
            format_func=get_meeting_label,
            help="Each analyzed audio file creates an independent meeting DB.",
        )
        if selected_meeting_id != st.session_state.get("active_meeting_id"):
            st.session_state["active_meeting_id"] = selected_meeting_id
            st.session_state["analysis_result"] = None
            st.rerun()
        current_db_path = get_meeting_db_path(selected_meeting_id, _config)
    else:
        st.info("No analyzed meetings yet. Upload audio above to get started.")

    st.divider()
    st.subheader("System Settings")
    st.info(f"**Model:** {_config.llm_model}")

    if current_db_path and st.session_state.get("active_meeting_id"):
        if st.button("Reset current meeting DB", type="secondary"):
            try:
                st.session_state["analysis_result"] = None
                st.session_state["active_meeting_id"] = None
                if os.path.exists(current_db_path):
                    time.sleep(0.1)
                    shutil.rmtree(current_db_path)
                st.success("Meeting DB has been reset.")
                time.sleep(0.5)
                st.rerun()
            except Exception as e:
                st.error(f"Reset failed: {e}")

# ── Audio analysis ────────────────────────────────────────────────────────────
if uploaded_audio:
    st.audio(uploaded_audio)

    if st.button("Analyze meeting", type="primary"):
        safe_filename = os.path.basename(uploaded_audio.name)
        temp_audio = os.path.join(_project_root, f"temp_{safe_filename}")

        with open(temp_audio, "wb") as f:
            f.write(uploaded_audio.getbuffer())

        # Pre-allocate the meeting ID so the DB directory path is known before processing.
        new_meeting_id = "m_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        new_db_path = get_meeting_db_path(new_meeting_id, _config)

        with st.status("Analyzing...", expanded=True) as status:
            try:
                engine = get_engine()
                result = engine.process(
                    temp_audio,
                    db_path=new_db_path,
                    meeting_title=meeting_title_input,
                    meeting_id=new_meeting_id,
                )
                if result:
                    st.session_state["active_meeting_id"] = new_meeting_id
                    st.session_state["analysis_result"] = result
                    current_db_path = new_db_path
                    status.update(
                        label="Analysis complete", state="complete", expanded=False
                    )
                else:
                    status.update(label="No content extracted", state="error")
                    st.warning("No analysis results were produced.")
            except Exception as e:
                st.error(f"Error: {e}")
                logger.error("Analysis error: %s", e, exc_info=True)
                status.update(label="Failed", state="error")

        if os.path.exists(temp_audio):
            try:
                os.remove(temp_audio)
            except OSError as e:
                logger.warning("Failed to remove temp file: %s", e)

elif not st.session_state["analysis_result"]:
    st.info("Upload a meeting recording or import a graph image to get started.")

    restored_data = vc.render_import_card_ui(share_mgr)
    if restored_data:
        bundle_format = (
            restored_data.get("format") if isinstance(restored_data, dict) else ""
        )
        if bundle_format == "speaknode_graph_bundle_v1":
            restored_analysis = restored_data.get("analysis_result", {})
            restored_graph_dump = restored_data.get("graph_dump", {})
        else:
            # Backward compatibility for legacy single-format PNG.
            restored_analysis = restored_data
            restored_graph_dump = {}

        st.session_state["analysis_result"] = restored_analysis

        # Restore into a fresh meeting DB directory.
        new_meeting_id = "m_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        new_db_path = get_meeting_db_path(new_meeting_id, _config)
        try:
            with KuzuManager(new_db_path, config=_config) as db_mgr:
                if restored_graph_dump:
                    db_mgr.restore_graph_dump(restored_graph_dump)
                    st.success("Full graph data restored and synced to DB.")
                else:
                    db_mgr.ingest_data(restored_analysis)
                    st.success("Analysis data restored and synced to DB.")
            st.session_state["active_meeting_id"] = new_meeting_id
            current_db_path = new_db_path
        except Exception as e:
            st.error(f"DB restore error: {e}")

        time.sleep(0.5)
        st.rerun()

# ── Main content ──────────────────────────────────────────────────────────────
if st.session_state["analysis_result"] and current_db_path:
    result = st.session_state["analysis_result"]
    active_meeting_id = st.session_state.get("active_meeting_id", "")

    st.divider()
    vc.display_analysis_cards(result)

    tab_graph, tab_agent, tab_save = st.tabs(["Knowledge Graph", "AI Agent", "Save"])

    with tab_graph:
        if os.path.exists(current_db_path):
            vc.render_graph_view(current_db_path)
            st.divider()
            vc.render_graph_editor(current_db_path)
        else:
            st.info("No graph data for this meeting yet.")

    with tab_agent:
        st.subheader("AI Agent")
        st.caption("Ask questions about meeting data. Email drafting is also supported.")
        history_key = f"agent_chat_history::{active_meeting_id}"

        if history_key not in st.session_state:
            st.session_state[history_key] = []
        chat_history = st.session_state[history_key]

        for msg in chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if not chat_history:
            st.markdown("**💡 예시 질문:**")
            example_cols = st.columns(3)
            examples = [
                "이번 회의에서 결정된 사항을 알려줘",
                "누가 어떤 할 일을 맡았어?",
                "회의 결과를 팀원에게 이메일로 보내줘",
            ]
            for i, example in enumerate(examples):
                if example_cols[i].button(example, key=f"example_{i}"):
                    st.session_state["_pending_agent_query"] = example
                    st.rerun()

        pending_query = st.session_state.pop("_pending_agent_query", None)
        user_input = st.chat_input("회의 데이터에 대해 질문하세요...")
        query = pending_query or user_input

        if query:
            chat_history.append({"role": "user", "content": query})
            with st.chat_message("user"):
                st.markdown(query)

            with st.chat_message("assistant"):
                with st.spinner("🔍 분석 중..."):
                    try:
                        engine = get_engine()
                        agent = engine.create_agent(db_path=current_db_path)

                        from langchain_core.messages import HumanMessage as HM, AIMessage as AM

                        lc_history = []
                        for msg in chat_history[:-1]:
                            if msg["role"] == "user":
                                lc_history.append(HM(content=msg["content"]))
                            else:
                                lc_history.append(AM(content=msg["content"]))

                        response = agent.query(query, chat_history=lc_history)
                        st.markdown(response)
                        chat_history.append({"role": "assistant", "content": response})
                    except Exception as e:
                        error_msg = f"❌ Agent 오류: {e}"
                        st.error(error_msg)
                        chat_history.append({"role": "assistant", "content": error_msg})

        if chat_history:
            if st.button("Clear chat", key="clear_agent_chat"):
                st.session_state[history_key] = []
                st.rerun()

    with tab_save:
        st.subheader("Save Knowledge Graph")
        st.info(
            "Export the current graph as a PNG image. "
            "Embedded data allows DB restoration when shared."
        )
        include_embeddings = st.checkbox(
            "Include embeddings (larger file, preserves vector search quality)",
            value=False,
            key="save_with_embeddings",
        )
        buf = vc.generate_static_graph_image(
            current_db_path,
            result,
            include_embeddings=include_embeddings,
        )
        if buf:
            st.download_button("Download graph", buf, "graph.png", "image/png")
