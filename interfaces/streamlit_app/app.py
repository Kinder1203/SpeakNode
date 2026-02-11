import streamlit as st
import os
import sys
import shutil

# 프로젝트 루트 경로 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../"))
sys.path.append(project_root)

import view_components as vc
from core.pipeline import main as run_pipeline
from core.share_manager import ShareManager

# --- 앱 설정 ---
st.set_page_config(page_title="SpeakNode Dashboard", layout="wide")
DB_PATH = os.path.join(project_root, "database", "speaknode.kuzu")
share_mgr = ShareManager()

# --- UI 렌더링 ---
vc.render_header()
uploaded_audio = vc.render_sidebar()

# DB 초기화 로직
if st.session_state.get('reset_db'):
    if os.path.exists(DB_PATH):
        shutil.rmtree(DB_PATH)
    st.success("데이터베이스가 초기화되었습니다.")
    st.session_state['reset_db'] = False
    st.rerun()

# --- 메인 시나리오 ---
if uploaded_audio:
    # 1. 오디오 미리듣기 (추가 제안 기능)
    st.audio(uploaded_audio)
    
    if st.button("🚀 회의 분석 시작", type="primary"):
        # 임시 저장
        temp_audio = os.path.join(project_root, f"temp_{uploaded_audio.name}")
        with open(temp_audio, "wb") as f:
            f.write(uploaded_audio.getbuffer())
        
        # 분석 진행 (Status UI 활용)
        with st.status("🔍 SpeakNode가 분석을 수행 중입니다...", expanded=True) as status:
            st.write("🎧 STT: 음성을 텍스트로 변환 중...")
            # pipeline 실행
            result = run_pipeline(temp_audio)
            
            st.write("🧠 LLM: 주요 정보를 구조화하고 요약 중...")
            st.write("💾 DB: 지식 그래프에 노드 및 엣지 생성 중...")
            status.update(label="✅ 분석이 완료되었습니다!", state="complete", expanded=False)
        
        # 2. 결과 출력 영역
        st.divider()
        vc.display_analysis_cards(result)
        
        # 3. 그래프 및 카드 영역 분할
        col_left, col_right = st.columns([2, 1])
        
        with col_left:
            vc.render_graph_view(DB_PATH)
            
        with col_right:
            st.subheader("🖼️ 요약 카드 발급")
            card_path = os.path.join(project_root, "shared_cards", "latest_summary.png")
            if os.path.exists(card_path):
                st.image(card_path, use_container_width=True)
                with open(card_path, "rb") as f:
                    st.download_button(
                        label="📥 요약 이미지 다운로드",
                        data=f,
                        file_name=f"SpeakNode_{uploaded_audio.name}.png",
                        mime="image/png"
                    )
        
        # 임시 오디오 삭제
        if os.path.exists(temp_audio):
            os.remove(temp_audio)
else:
    # 업로드 전 기본 화면: 가이드 혹은 데이터 불러오기
    st.info("왼쪽 사이드바에서 회의 녹음 파일을 업로드하여 분석을 시작하세요.")
    vc.render_import_card_ui(share_mgr)

# --- 푸터 ---
st.caption("SpeakNode v1.0 (Prototype) | Kotlin Body x Python Brain Architecture")