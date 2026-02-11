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

# --- UI 렌더링 ---
vc.render_header()

with st.sidebar:
    st.header("📂 Workspace")
    uploaded_audio = st.file_uploader("회의 녹음 파일", type=["mp3", "wav", "m4a"])
    st.divider()
    st.info(f"**Model:** DeepSeek-R1-14B")
    
    # [Fix: High] DB 초기화 로직 강화 (파일/폴더 구분 삭제)
    if st.button("🗑️ DB 초기화", type="secondary"):
        try:
            st.session_state['analysis_result'] = None
            
            if os.path.exists(DB_PATH):
                # 잠금 해제를 위해 잠시 대기
                time.sleep(0.1)
                
                if os.path.isfile(DB_PATH):
                    os.remove(DB_PATH) # 파일이면 remove
                else:
                    shutil.rmtree(DB_PATH) # 폴더면 rmtree (ignore_errors 제거하여 에러 확인)
                
            st.success("DB가 초기화되었습니다.")
            time.sleep(0.5)
            st.rerun()
        except Exception as e:
            st.error(f"초기화 실패: {e}")
            # 실패 시 로그 출력
            print(f"❌ DB Deletion Failed: {e}")

# --- 메인 시나리오 ---
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
                # Engine Process 호출
                result = engine.process(temp_audio)
                st.session_state['analysis_result'] = result
                
                if result:
                    status.update(label="✅ 완료!", state="complete")
                else:
                    status.update(label="⚠️ 내용 없음", state="error")
                    st.warning("분석 결과가 없습니다. (녹음 상태를 확인해주세요)")
            except Exception as e:
                st.error(f"에러: {e}")
                status.update(label="❌ 실패", state="error")
        
        if os.path.exists(temp_audio):
            os.remove(temp_audio)

    # 결과 표시
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
            db = KuzuManager(DB_PATH)
            db.ingest_data(restored)
            st.session_state['analysis_result'] = restored
            st.rerun()