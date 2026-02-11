import streamlit as st
import os
import sys
import shutil
import time
import re

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../"))
sys.path.append(project_root)

import view_components as vc
from core.pipeline import SpeakNodeEngine
from core.share_manager import ShareManager
from core.kuzu_manager import KuzuManager

# --- 앱 기본 설정 ---
st.set_page_config(page_title="SpeakNode Dashboard", layout="wide")
CHAT_DB_DIR = os.path.join(project_root, "database", "chats")
os.makedirs(CHAT_DB_DIR, exist_ok=True)
share_mgr = ShareManager()

# --- 엔진 캐싱 ---
@st.cache_resource
def get_engine():
    return SpeakNodeEngine()

# --- 세션 상태 초기화 ---
if 'analysis_result' not in st.session_state:
    st.session_state['analysis_result'] = None
if "active_chat_id" not in st.session_state:
    st.session_state["active_chat_id"] = "default"


def sanitize_chat_id(raw: str) -> str:
    safe = re.sub(r"[^0-9A-Za-z_-]+", "_", (raw or "").strip()).strip("_")
    return safe or "default"


def list_chat_ids() -> list[str]:
    chat_ids = []
    for name in os.listdir(CHAT_DB_DIR):
        if name.endswith(".kuzu"):
            chat_ids.append(name[:-5])
    return sorted(chat_ids)


def get_chat_db_path(chat_id: str) -> str:
    return os.path.join(CHAT_DB_DIR, f"{sanitize_chat_id(chat_id)}.kuzu")

# --- [사이드바] 파일 업로드 및 설정 ---
vc.render_header()

with st.sidebar:
    st.header("📂 Workspace")
    # 오디오 업로드
    uploaded_audio = st.file_uploader("회의 녹음 파일 (분석용)", type=["mp3", "wav", "m4a"])
    
    st.divider()
    st.subheader("💬 Chat Sessions")

    chat_ids = list_chat_ids()
    active_chat_id = sanitize_chat_id(st.session_state["active_chat_id"])
    if active_chat_id not in chat_ids:
        chat_ids = [active_chat_id] + chat_ids

    selected_chat_id = st.selectbox(
        "채팅 선택",
        options=chat_ids if chat_ids else ["default"],
        index=(chat_ids.index(active_chat_id) if chat_ids else 0),
        help="같은 채팅은 누적 저장, 다른 채팅은 다른 DB를 사용합니다.",
    )

    if selected_chat_id != st.session_state["active_chat_id"]:
        st.session_state["active_chat_id"] = selected_chat_id
        st.session_state["analysis_result"] = None
        st.rerun()

    new_chat_name = st.text_input("새 채팅 이름", placeholder="예: genomics_review")
    if st.button("➕ 새 채팅 생성", use_container_width=True):
        new_chat_id = sanitize_chat_id(new_chat_name)
        st.session_state["active_chat_id"] = new_chat_id
        st.session_state["analysis_result"] = None
        st.success(f"채팅 '{new_chat_id}' 생성 완료")
        st.rerun()

    current_db_path = get_chat_db_path(st.session_state["active_chat_id"])

    st.divider()
    st.subheader("⚙️ System Settings")
    st.info(f"**Model:** qwen2.5:14b\n\n**Active Chat:** {st.session_state['active_chat_id']}")

    if st.button("🗑️ 현재 채팅 DB 초기화", type="secondary"):
        try:
            st.session_state['analysis_result'] = None
            if os.path.exists(current_db_path):
                time.sleep(0.1)
                if os.path.isfile(current_db_path):
                    os.remove(current_db_path)
                else:
                    shutil.rmtree(current_db_path)
            st.success("현재 채팅 DB가 초기화되었습니다.")
            time.sleep(0.5)
            st.rerun()
        except Exception as e:
            st.error(f"초기화 실패: {e}")

# --- [메인 로직] 1. 분석 (오디오 업로드 시) ---
if uploaded_audio:
    st.audio(uploaded_audio)
    
    if st.button("🚀 회의 분석 시작", type="primary"):
        safe_filename = os.path.basename(uploaded_audio.name)
        temp_audio = os.path.join(project_root, f"temp_{safe_filename}")
        
        with open(temp_audio, "wb") as f:
            f.write(uploaded_audio.getbuffer())
        
        with st.status("🔍 분석 중...", expanded=True) as status:
            engine = get_engine()
            try:
                result = engine.process(temp_audio, db_path=current_db_path)
                st.session_state['analysis_result'] = result
                
                if result:
                    status.update(label="✅ 분석 완료!", state="complete", expanded=False)
                else:
                    status.update(label="⚠️ 내용 없음", state="error")
                    st.warning("분석 결과가 없습니다.")
            except Exception as e:
                st.error(f"에러: {e}")
                status.update(label="❌ 실패", state="error")
        
        if os.path.exists(temp_audio):
            os.remove(temp_audio)

# --- [메인 로직] 2. 복원 (오디오 없을 때 PNG 업로드) ---
elif not st.session_state['analysis_result']: 
    st.info("회의 파일을 업로드하거나, 기존 그래프 이미지를 통해 복원하세요.")
    
    restored_data = vc.render_import_card_ui(share_mgr)
    if restored_data:
        st.session_state['analysis_result'] = restored_data
        
        # [Medium Fix] KuzuManager 인스턴스 생성 및 명시적 종료
        db_mgr = None
        try:
            db_mgr = KuzuManager(current_db_path)
            db_mgr.ingest_data(restored_data)
            st.success("✅ 데이터 복원 및 DB 동기화 완료!")
        except Exception as e:
            st.error(f"❌ DB 복원 중 오류: {e}")
        finally:
            if db_mgr:
                db_mgr.close() # 리소스 해제
            
        time.sleep(0.5)
        st.rerun()

# --- [공통] 대시보드 출력 (오디오 여부와 상관없이 결과가 있으면 출력) ---
if st.session_state['analysis_result']:
    result = st.session_state['analysis_result']
    
    st.divider()
    vc.display_analysis_cards(result)
    
    c1, c2 = st.columns([2, 1])
    
    with c1:
        if os.path.exists(current_db_path):
            vc.render_graph_view(current_db_path)
        else:
            st.info("현재 채팅에는 아직 저장된 그래프 데이터가 없습니다.")
        
    with c2:
        st.subheader("💾 저장")
        st.info("현재 결과를 지식 그래프 이미지로 저장합니다.")
        buf = vc.generate_static_graph_image(current_db_path, result)
        if buf:
            st.download_button("📥 그래프 다운로드", buf, "graph.png", "image/png")
