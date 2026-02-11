import streamlit as st
import os
import sys
import shutil
import networkx as nx
from pyvis.network import Network
import kuzu
import streamlit.components.v1 as components

# [중요] Core 모듈을 가져오기 위해 상위 경로 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../"))
sys.path.append(project_root)

# Core 모듈 임포트
try:
    from core.pipeline import main as run_pipeline
    from core.share_manager import ShareManager
except ImportError as e:
    st.error(f"❌ Core 모듈을 찾을 수 없습니다: {e}")
    st.stop()

# --- 설정 ---
st.set_page_config(page_title="SpeakNode Prototype", layout="wide", page_icon="🧠")
DB_PATH = os.path.join(project_root, "database", "speaknode.kuzu")

# --- UI 헤더 ---
st.title("🧠 SpeakNode: AI Meeting Analyst")
st.markdown("RunPod Local Environment | Track A: Prototyping")

# --- 사이드바: 파일 업로드 ---
with st.sidebar:
    st.header("📂 회의 녹음 파일 업로드")
    uploaded_file = st.file_uploader("MP3, WAV 파일을 드래그하세요", type=["mp3", "wav", "m4a"])
    
    if st.button("🔄 초기화 (DB 삭제)"):
        # 테스트를 위해 DB 날리는 버튼
        if os.path.exists(DB_PATH):
            shutil.rmtree(DB_PATH)
            st.warning("데이터베이스가 초기화되었습니다.")

# --- 메인 로직 ---
if uploaded_file:
    # 1. 임시 파일 저장
    temp_path = os.path.join(project_root, f"temp_{uploaded_file.name}")
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    st.info(f"파일 업로드 완료: {uploaded_file.name}")

    # 2. 분석 시작 버튼
    if st.button("🚀 분석 시작 (Analyze)"):
        with st.status("🤖 AI가 회의를 분석 중입니다...", expanded=True) as status:
            st.write("👂 1. STT: 음성 듣는 중... (Whisper)")
            # 파이프라인 실행
            result = run_pipeline(temp_path)
            
            st.write("🧠 2. Extraction: 내용 요약 및 구조화 중... (DeepSeek)")
            st.write("💾 3. Ingest: 지식 그래프 저장 중... (KuzuDB)")
            st.write("🖼️ 4. Share: 요약 카드 생성 중...")
            status.update(label="✅ 분석 완료!", state="complete", expanded=False)
        
        # 3. 결과 화면 분할
        col1, col2 = st.columns([1, 1])

        with col1:
            st.subheader("📝 분석 요약")
            if result and 'topics' in result:
                for topic in result['topics']:
                    st.success(f"**주제:** {topic['title']}")
                    st.write(topic.get('summary', ''))
            
            st.subheader("🖼️ 공유용 카드")
            card_path = os.path.join(project_root, "shared_cards", "latest_summary.png")
            if os.path.exists(card_path):
                st.image(card_path, caption="Meeting Summary Card", use_container_width=True)
                with open(card_path, "rb") as file:
                    st.download_button(
                        label="카드 다운로드",
                        data=file,
                        file_name="meeting_card.png",
                        mime="image/png"
                    )

        with col2:
            st.subheader("🕸️ 지식 그래프 (Knowledge Graph)")
            # KuzuDB에서 데이터 꺼내서 시각화
            try:
                db = kuzu.Database(DB_PATH)
                conn = kuzu.Connection(db)
                
                # PyVis 네트워크 생성
                net = Network(height="500px", width="100%", bgcolor="#222222", font_color="white", notebook=False)
                
                # 노드 가져오기 (Topic, Person)
                nodes = conn.execute("MATCH (t:Topic) RETURN t.title").as_numpy()
                for row in nodes:
                    net.add_node(row[0], label=row[0], color="#00ff80", title="Topic")
                
                nodes_p = conn.execute("MATCH (p:Person) RETURN p.name").as_numpy()
                for row in nodes_p:
                    net.add_node(row[0], label=row[0], color="#ff0080", title="Person")

                # 엣지 가져오기 (Person -> Topic)
                edges = conn.execute("MATCH (p:Person)-[:PROPOSED]->(t:Topic) RETURN p.name, t.title").as_numpy()
                for row in edges:
                    net.add_edge(row[0], row[1], title="PROPOSED")

                # 그래프 저장 및 표시
                graph_html = os.path.join(current_dir, "graph.html")
                net.save_graph(graph_html)
                
                # Streamlit에 HTML 임베딩
                with open(graph_html, 'r', encoding='utf-8') as f:
                    source_code = f.read() 
                components.html(source_code, height=510)
                
            except Exception as e:
                st.error(f"그래프 시각화 오류: {e}")
                st.write("데이터가 아직 충분하지 않거나 DB 경로 문제일 수 있습니다.")

    # 청소
    if os.path.exists(temp_path):
        os.remove(temp_path)

else:
    st.info("좌측 사이드바에서 오디오 파일을 업로드해주세요.")