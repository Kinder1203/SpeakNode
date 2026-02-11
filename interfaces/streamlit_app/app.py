import streamlit as st
import os
import sys
import shutil
import time

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../"))
sys.path.append(project_root)

import view_components as vc
from core.pipeline import SpeakNodeEngine
from core.share_manager import ShareManager
from core.kuzu_manager import KuzuManager

st.set_page_config(page_title="SpeakNode Dashboard", layout="wide")
DB_PATH = os.path.join(project_root, "database", "speaknode.kuzu")
share_mgr = ShareManager()

@st.cache_resource
def get_engine():
    return SpeakNodeEngine()

if 'analysis_result' not in st.session_state:
    st.session_state['analysis_result'] = None

# --- 사이드바 및 DB 초기화 로직 (직접 구현) ---
vc.render_header()

with st.sidebar:
    st.header("📂 Workspace")
    uploaded_audio = st.file_uploader("회의 녹음 파일", type=["mp3", "wav", "m4a"])
    st.divider()
    st.info(f"**Model:** DeepSeek-R1-14B")
    
    # [Fix] 초기화 버튼을 여기서 직접 처리
    if st.button("🗑️ DB 초기화", type="secondary"):
        try:
            st.session_state['analysis_result'] = None
            
            if os.path.exists(DB_PATH):
                # KuzuDB는 폴더로 생성됨. 파일 잠금 이슈 방지를 위해 약간의 대기 후 삭제
                time.sleep(0.1) 
                shutil.rmtree(DB_PATH, ignore_errors=True)
                
            st.success("DB가 초기화되었습니다.")
            time.sleep(0.5)
            st.rerun()
        except Exception as e:
            st.error(f"초기화 실패 (파일 사용 중): {e}")

# --- 메인 로직 ---
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
                # [Fix] engine.process는 이제 내부에서 절대경로 DB_PATH를 사용함
                result = engine.process(temp_audio)
                st.session_state['analysis_result'] = result
                
                if result:
                    status.update(label="✅ 완료!", state="complete")
                else:
                    status.update(label="⚠️ 내용 없음", state="error")
            except Exception as e:
                st.error(f"에러: {e}")
                status.update(label="❌ 실패", state="error")
        
        if os.path.exists(temp_audio):
            os.remove(temp_audio)

    if st.session_state['analysis_result']:
        result = st.session_state['analysis_result']
        st.divider()
        vc.display_analysis_cards(result)
        
        c1, c2 = st.columns([2, 1])
        with c1: vc.render_graph_view(DB_PATH)
        with c2:
            st.subheader("💾 저장")
            buf = vc.generate_static_graph_image(DB_PATH, result)
            if buf:
                st.download_button("📥 그래프 다운로드", buf, "graph.png", "image/png")

else:
    st.info("파일을 업로드하세요.")
    restored = vc.render_import_card_ui(share_mgr)
    if restored:
        if st.button("🔄 복원하기"):
            db = KuzuManager(DB_PATH) # [Fix] 절대경로 주입
            db.ingest_data(restored)
            st.session_state['analysis_result'] = restored
            st.rerun()