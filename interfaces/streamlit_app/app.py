import streamlit as st
import os
import sys
import shutil
import time
import re

# [Fix 1] set_page_config를 최상단으로 이동 (가장 중요)
st.set_page_config(page_title="SpeakNode Dashboard", layout="wide")

# [Fix 3] Matplotlib 백엔드 설정 (서버 환경 프리징 방지)
import matplotlib
matplotlib.use('Agg') # 화면 출력 없는 모드로 강제 설정

import view_components as vc
from core.pipeline import SpeakNodeEngine
from core.shared.share_manager import ShareManager
from core.db.kuzu_manager import KuzuManager
from core.config import SpeakNodeConfig, sanitize_chat_id, get_chat_db_path, list_chat_ids

_config = SpeakNodeConfig()
CHAT_DB_DIR = _config.db_base_dir
os.makedirs(CHAT_DB_DIR, exist_ok=True)

# ShareManager 초기화
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
SHARED_CARDS_DIR = os.path.join(project_root, "shared_cards")
share_mgr = ShareManager(output_dir=SHARED_CARDS_DIR)

# --- 엔진 캐싱 ---
@st.cache_resource
def get_engine():
    print("🏗️ [App] Initializing SpeakNodeEngine...")
    return SpeakNodeEngine()

# --- 세션 상태 초기화 ---
if 'analysis_result' not in st.session_state:
    st.session_state['analysis_result'] = None
if "active_chat_id" not in st.session_state:
    st.session_state["active_chat_id"] = "default"



# --- [사이드바] 파일 업로드 및 설정 ---
vc.render_header()

with st.sidebar:
    st.header("📂 Workspace")
    # 오디오 업로드
    uploaded_audio = st.file_uploader("회의 녹음 파일 (분석용)", type=["mp3", "wav", "m4a"])
    
    st.divider()
    st.subheader("💬 Chat Sessions")

    chat_ids = list_chat_ids(_config)
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

    current_db_path = get_chat_db_path(st.session_state["active_chat_id"], _config)

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
            try:
                # [Fix] 엔진 로딩을 try 블록 안에서 수행하여 에러 캐치
                engine = get_engine()
                result = engine.process(temp_audio, db_path=current_db_path)
                st.session_state['analysis_result'] = result
                
                if result:
                    status.update(label="✅ 분석 완료!", state="complete", expanded=False)
                else:
                    status.update(label="⚠️ 내용 없음", state="error")
                    st.warning("분석 결과가 없습니다.")
            except Exception as e:
                st.error(f"에러 발생: {e}")
                print(f"❌ Error detail: {e}")
                status.update(label="❌ 실패", state="error")
        
        if os.path.exists(temp_audio):
            try:
                os.remove(temp_audio)
            except: pass

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
    
    # --- 탭 레이아웃: 그래프 / AI Agent / 저장 ---
    tab_graph, tab_agent, tab_save = st.tabs(["🕸️ Knowledge Graph", "🤖 AI Agent", "💾 저장"])
    
    with tab_graph:
        if os.path.exists(current_db_path):
            vc.render_graph_view(current_db_path)
        else:
            st.info("현재 채팅에는 아직 저장된 그래프 데이터가 없습니다.")

    with tab_agent:
        st.subheader("🤖 AI Agent — 회의 데이터 질의")
        st.caption("회의 내용에 대해 자유롭게 질문하세요. 이메일 초안 작성도 가능합니다.")
        
        # 세션 상태: Agent 대화 히스토리
        if "agent_chat_history" not in st.session_state:
            st.session_state["agent_chat_history"] = []
        
        # 이전 대화 표시
        for msg in st.session_state["agent_chat_history"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
        
        # 예시 질문 버튼
        if not st.session_state["agent_chat_history"]:
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
        
        # 채팅 입력
        pending_query = st.session_state.pop("_pending_agent_query", None)
        user_input = st.chat_input("회의 데이터에 대해 질문하세요...")
        query = pending_query or user_input
        
        if query:
            # 사용자 메시지 표시 & 저장
            st.session_state["agent_chat_history"].append({"role": "user", "content": query})
            with st.chat_message("user"):
                st.markdown(query)
            
            # Agent 실행
            with st.chat_message("assistant"):
                with st.spinner("🔍 분석 중..."):
                    try:
                        engine = get_engine()
                        agent = engine.create_agent(db_path=current_db_path)
                        
                        # LangChain 메시지 히스토리 구성
                        from langchain_core.messages import HumanMessage as HM, AIMessage as AM
                        lc_history = []
                        for msg in st.session_state["agent_chat_history"][:-1]:  # 현재 질문 제외
                            if msg["role"] == "user":
                                lc_history.append(HM(content=msg["content"]))
                            else:
                                lc_history.append(AM(content=msg["content"]))
                        
                        response = agent.query(query, chat_history=lc_history)
                        st.markdown(response)
                        st.session_state["agent_chat_history"].append({"role": "assistant", "content": response})
                    except Exception as e:
                        error_msg = f"❌ Agent 오류: {e}"
                        st.error(error_msg)
                        st.session_state["agent_chat_history"].append({"role": "assistant", "content": error_msg})
        
        # 대화 초기화 버튼
        if st.session_state["agent_chat_history"]:
            if st.button("🗑️ 대화 초기화", key="clear_agent_chat"):
                st.session_state["agent_chat_history"] = []
                st.rerun()

    with tab_save:
        st.subheader("💾 지식 그래프 이미지 저장")
        st.info("현재 결과를 지식 그래프 이미지로 저장합니다. PNG에 데이터가 포함되어 공유 시 DB 복원이 가능합니다.")
        buf = vc.generate_static_graph_image(current_db_path, result)
        if buf:
            st.download_button("📥 그래프 다운로드", buf, "graph.png", "image/png")