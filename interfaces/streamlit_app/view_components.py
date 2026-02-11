import streamlit as st
import os
import pandas as pd
from pyvis.network import Network
import streamlit.components.v1 as components
import kuzu

def render_header():
    """상단 헤더 및 프로젝트 소개"""
    st.title("🧠 SpeakNode: Intelligent Meeting Analyst")
    st.markdown("""
    **Local AI 기반 회의록 지식화 시스템** STT(Whisper) + LLM(DeepSeek) + GraphDB(KuzuDB)를 활용하여 회의 내용을 구조화합니다.
    """)
    st.divider()

def render_sidebar():
    """사이드바 설정 및 파일 업로드"""
    with st.sidebar:
        st.header("📂 Workspace")
        uploaded_file = st.file_uploader("회의 녹음 파일 (MP3, WAV)", type=["mp3", "wav", "m4a"])
        
        st.divider()
        st.subheader("⚙️ System Settings")
        st.info(f"**Model:** DeepSeek-R1-14B\n\n**STT:** Faster-Whisper-V3")
        
        if st.button("🗑️ DB 초기화", help="모든 회의 데이터를 삭제합니다."):
            st.session_state['reset_db'] = True
            
        return uploaded_file

def display_analysis_cards(result):
    """분석 결과(주제, 결정사항, 할 일)를 카드 형태로 출력"""
    if not result:
        return

    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("📌 주요 주제")
        for t in result.get('topics', []):
            with st.expander(f"📍 {t['title']}"):
                st.write(t.get('summary', '내용 없음'))

    with col2:
        st.subheader("✅ 결정 사항")
        for d in result.get('decisions', []):
            st.success(d.get('description', d.get('desc', '')))

    with col3:
        st.subheader("📋 할 일 (Tasks)")
        tasks = result.get('tasks', [])
        if tasks:
            df = pd.DataFrame(tasks)
            st.dataframe(df, use_container_width=True)
        else:
            st.write("추출된 할 일이 없습니다.")

def render_graph_view(db_path):
    """KuzuDB 데이터를 시각적 네트워크 그래프로 렌더링"""
    st.subheader("🕸️ Knowledge Graph Explorer")
    
    try:
        db = kuzu.Database(db_path)
        conn = kuzu.Connection(db)
        
        # 그래프 설정 (흰색 배경, 진한 글씨)
        net = Network(height="500px", width="100%", bgcolor="#ffffff", font_color="#333333")
        
        # 1. Decision 노드 추가 (노란색)
        nodes_d_result = conn.execute("MATCH (d:Decision) RETURN d.description")
        while nodes_d_result.has_next():
            row = nodes_p_result.get_next()
            net.add_node(row[0], label=row[0], color="#f1c40f", shape="triangle", title="Decision")

        # 2. Task 노드 추가 (파란색)
        nodes_task_result = conn.execute("MATCH (t:Task) RETURN t.description")
        while nodes_task_result.has_next():
            row = nodes_task_result.get_next()
            net.add_node(row[0], label=row[0], color="#3498db", shape="dot", title="Task")

        # 3. 관계 추가 (Topic -> Decision, Person -> Task 등)
        # RESULTED_IN 관계 (Topic -> Decision)
        edges_res_result = conn.execute("MATCH (t:Topic)-[:RESULTED_IN]->(d:Decision) RETURN t.title, d.description")
        while edges_res_result.has_next():
            row = edges_res_result.get_next()
            net.add_edge(row[0], row[1], label="RESULTED_IN", color="#bdc3c7")

        # ASSIGNED_TO 관계 (Person -> Task)
        edges_ass_result = conn.execute("MATCH (p:Person)-[:ASSIGNED_TO]->(t:Task) RETURN p.name, t.description")
        while edges_ass_result.has_next():
            row = edges_ass_result.get_next()
            net.add_edge(row[0], row[1], label="ASSIGNED_TO", color="#bdc3c7")

        # 물리 엔진 설정 및 HTML 생성
        net.toggle_physics(True)
        path = "graph.html"
        net.save_graph(path)
        
        # Streamlit에 그래프 삽입
        with open(path, 'r', encoding='utf-8') as f:
            components.html(f.read(), height=550)
            
    except Exception as e:
        # 데이터가 아예 없거나 테이블이 생성되지 않았을 때 표시
        st.warning(f"그래프를 구성할 데이터가 부족하거나 오류가 발생했습니다: {e}")

def render_import_card_ui(share_manager):
    """공유 카드로부터 데이터 복원하는 UI"""
    st.divider()
    st.subheader("📥 공유 카드로 데이터 불러오기")
    import_file = st.file_uploader("SpeakNode 요약 카드(PNG)를 업로드하세요", type=["png"], key="import_card")
    
    if import_file:
        # 임시 저장 후 데이터 추출
        temp_path = f"temp_import_{import_file.name}"
        with open(temp_path, "wb") as f:
            f.write(import_file.getbuffer())
        
        data = share_manager.load_data_from_image(temp_path)
        if data:
            st.success("✅ 카드에서 회의 데이터를 성공적으로 추출했습니다!")
            st.json(data)
        else:
            st.error("❌ 이 이미지에는 SpeakNode 메타데이터가 포함되어 있지 않습니다.")
        
        if os.path.exists(temp_path):
            os.remove(temp_path)