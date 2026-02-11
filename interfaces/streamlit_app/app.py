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

# --- 앱 기본 설정 ---
st.set_page_config(page_title="SpeakNode Dashboard", layout="wide")
DB_PATH = os.path.join(project_root, "database", "speaknode.kuzu")
share_mgr = ShareManager()

# --- 엔진 캐싱 ---
@st.cache_resource
def get_engine():
    return SpeakNodeEngine()

# --- 세션 상태 초기화 ---
if 'analysis_result' not in st.session_state:
    st.session_state['analysis_result'] = None

# --- [사이드바] 파일 업로드 및 설정 ---
vc.render_header()

with st.sidebar:
    st.header("📂 Workspace")
    # 오디오 업로드
    uploaded_audio = st.file_uploader("회의 녹음 파일 (분석용)", type=["mp3", "wav", "m4a"])
    
    st.divider()
    
    # PNG 업로드 (복원용) - 사이드바에 통합하거나 메인화면에 둘 수 있음.
    # 여기서는 편의를 위해 사이드바 아래쪽에 배치하거나, 오디오가 없을 때 메인에 띄웁니다.
    
    st.subheader("⚙️ System Settings")
    st.info(f"**Model:** qwen2.5:14b") # 오타 수정: **Model:** 로 변경
    
    if st.button("🗑️ DB 초기화", type="secondary"):
        try:
            st.session_state['analysis_result'] = None
            if os.path.exists(DB_PATH):
                time.sleep(0.1)
                if os.path.isfile(DB_PATH):
                    os.remove(DB_PATH)
                else:
                    shutil.rmtree(DB_PATH)
            st.success("DB가 초기화되었습니다.")
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
                result = engine.process(temp_audio)
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
    # 결과도 없고 오디오도 없으면 -> "파일을 올리거나 복원하세요" 화면
    st.info("좌측에서 **회의 녹음 파일**을 업로드하거나, 아래에서 **지식 그래프 이미지**를 업로드하여 복원하세요.")
    
    # PNG 복원 UI
    restored_data = vc.render_import_card_ui(share_mgr)
    if restored_data:
        # 데이터가 복원되면 바로 세션에 넣고 리런! (버튼 불필요)
        st.session_state['analysis_result'] = restored_data
        
        # DB에도 반영 (선택사항, 그래프 뷰를 위해 필요)
        try:
            db = KuzuManager(DB_PATH)
            db.ingest_data(restored_data)
        except Exception:
            pass # 이미 있을 수 있음
            
        st.success("✅ 데이터 복원 완료! 대시보드를 불러옵니다...")
        time.sleep(0.5)
        st.rerun()

# --- [공통] 대시보드 출력 (오디오 여부와 상관없이 결과가 있으면 출력) ---
if st.session_state['analysis_result']:
    result = st.session_state['analysis_result']
    
    st.divider()
    vc.display_analysis_cards(result)
    
    c1, c2 = st.columns([2, 1])
    
    with c1:
        # DB 경로에 데이터가 있어야 그래프가 그려짐. 
        # 복원 직후라면 위에서 ingest_data를 했으므로 정상 작동.
        vc.render_graph_view(DB_PATH)
        
    with c2:
        st.subheader("💾 저장")
        st.info("현재 결과를 지식 그래프 이미지로 저장합니다.")
        buf = vc.generate_static_graph_image(DB_PATH, result)
        if buf:
            st.download_button("📥 그래프 다운로드", buf, "graph.png", "image/png")