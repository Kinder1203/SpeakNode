import streamlit as st
import os
import pandas as pd
from pyvis.network import Network
import streamlit.components.v1 as components
import kuzu
import networkx as nx
import matplotlib.pyplot as plt
from PIL import Image
from PIL.PngImagePlugin import PngInfo
import io
import json

# --- 폰트 설정 (리눅스/윈도우 호환) ---
def set_korean_font():
    """OS에 따른 한글 폰트 설정"""
    try:
        if os.name == 'posix':  # Linux
            plt.rcParams['font.family'] = 'NanumGothic' 
        else:  # Windows
            plt.rcParams['font.family'] = 'Malgun Gothic'
        plt.rcParams['axes.unicode_minus'] = False
    except Exception:
        pass

# ... (render_header, render_sidebar, display_analysis_cards, render_graph_view는 기존과 동일하게 유지) ...
# (코드 길이상 생략했지만, 기존에 작성해주신 render_graph_view를 그대로 쓰시면 됩니다)

def render_header():
    st.title("🧠 SpeakNode: Intelligent Meeting Analyst")
    st.markdown("**Local AI 기반 회의록 지식화 시스템**")
    st.divider()

def render_sidebar():
    with st.sidebar:
        st.header("📂 Workspace")
        return st.file_uploader("회의 녹음 파일 (MP3, WAV)", type=["mp3", "wav", "m4a"])

def display_analysis_cards(result):
    if not result: return
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("📌 주제")
        for t in result.get('topics', []):
            with st.expander(t['title']): st.write(t.get('summary', ''))
    with c2:
        st.subheader("✅ 결정")
        for d in result.get('decisions', []): st.success(d.get('description', ''))
    with c3:
        st.subheader("📋 할 일")
        if result.get('tasks'): st.dataframe(result['tasks'])

def render_graph_view(db_path):
    st.subheader("🕸️ Knowledge Graph Explorer")
    db = None
    conn = None
    try:
        db = kuzu.Database(db_path)
        conn = kuzu.Connection(db)
        net = Network(height="500px", width="100%", bgcolor="#ffffff", font_color="#333333")
        
        # Nodes
        try:
            nodes_p = conn.execute("MATCH (p:Person) RETURN p.name, p.role")
            while nodes_p.has_next():
                row = nodes_p.get_next()
                person_name = row[0]
                person_role = row[1] if row[1] else "Member"
                net.add_node(
                    f"person::{person_name}",
                    label=f"{person_name}\n({person_role})",
                    color="#2ecc71",
                    title=person_role,
                )
        except: pass
        
        try:
            nodes_t = conn.execute("MATCH (t:Topic) RETURN t.title")
            while nodes_t.has_next():
                row = nodes_t.get_next()
                title = row[0]
                net.add_node(f"topic::{title}", label=title, color="#9b59b6", shape="box")
        except: pass

        try:
            nodes_d = conn.execute("MATCH (d:Decision) RETURN d.description")
            while nodes_d.has_next():
                row = nodes_d.get_next()
                desc = row[0]
                net.add_node(f"decision::{desc}", label=desc, color="#f1c40f", shape="triangle")
        except: pass

        try:
            nodes_task = conn.execute("MATCH (t:Task) RETURN t.description")
            while nodes_task.has_next():
                row = nodes_task.get_next()
                desc = row[0]
                net.add_node(f"task::{desc}", label=desc, color="#3498db", shape="dot")
        except: pass

        # Edges
        edges_res = conn.execute("MATCH (t:Topic)-[:RESULTED_IN]->(d:Decision) RETURN t.title, d.description")
        while edges_res.has_next():
            row = edges_res.get_next()
            net.add_edge(f"topic::{row[0]}", f"decision::{row[1]}", label="RESULTED_IN")

        edges_ass = conn.execute("MATCH (p:Person)-[:ASSIGNED_TO]->(t:Task) RETURN p.name, t.description")
        while edges_ass.has_next():
            row = edges_ass.get_next()
            net.add_edge(f"person::{row[0]}", f"task::{row[1]}", label="ASSIGNED_TO")

        edges_prop = conn.execute("MATCH (p:Person)-[:PROPOSED]->(t:Topic) RETURN p.name, t.title")
        while edges_prop.has_next():
            row = edges_prop.get_next()
            net.add_edge(f"person::{row[0]}", f"topic::{row[1]}", label="PROPOSED")

        if not net.nodes:
            st.info("그래프에 표시할 노드가 아직 없습니다.")
            return

        net.toggle_physics(True)
        # 파일 캐시/잔상 방지를 위해 메모리 HTML로 직접 렌더링
        components.html(net.generate_html(notebook=False), height=550)
    except Exception as e:
        st.error(f"그래프 렌더링 오류: {e}")
    finally:
        try:
            if conn is not None and hasattr(conn, "close"):
                conn.close()
            if db is not None and hasattr(db, "close"):
                db.close()
        except Exception:
            pass

def generate_static_graph_image(db_path, analysis_json):
    """지식 그래프를 PNG 이미지로 저장 (Task 노드 누락 수정됨)"""
    set_korean_font()
    db = None
    conn = None
    try:
        db = kuzu.Database(db_path)
        conn = kuzu.Connection(db)
        
        G = nx.DiGraph()
        labels = {}

        # 1. Person 노드
        nodes_p = conn.execute("MATCH (p:Person) RETURN p.name")
        while nodes_p.has_next():
            row = nodes_p.get_next()
            G.add_node(row[0], color="#2ecc71")
            labels[row[0]] = row[0]
        
        # 2. Topic 노드
        nodes_t = conn.execute("MATCH (t:Topic) RETURN t.title")
        while nodes_t.has_next():
            row = nodes_t.get_next()
            G.add_node(row[0], color="#9b59b6")
            labels[row[0]] = row[0]

        # 3. Decision 노드
        nodes_d = conn.execute("MATCH (d:Decision) RETURN d.description")
        while nodes_d.has_next():
            row = nodes_d.get_next()
            label = (row[0][:10] + '..') if len(row[0]) > 10 else row[0]
            G.add_node(row[0], color="#f1c40f")
            labels[row[0]] = label

        # [Fix] 4. Task 노드 (누락되었던 부분 확인 및 보강)
        nodes_task = conn.execute("MATCH (t:Task) RETURN t.description")
        while nodes_task.has_next():
            row = nodes_task.get_next()
            label = (row[0][:10] + '..') if len(row[0]) > 10 else row[0]
            G.add_node(row[0], color="#3498db")
            labels[row[0]] = label

        # 5. 엣지 연결 (노드가 존재할 때만 추가)
        # Topic -> Decision
        edges_res = conn.execute("MATCH (t:Topic)-[:RESULTED_IN]->(d:Decision) RETURN t.title, d.description")
        while edges_res.has_next():
            row = edges_res.get_next()
            if G.has_node(row[0]) and G.has_node(row[1]): G.add_edge(row[0], row[1])

        # Person -> Task
        edges_ass = conn.execute("MATCH (p:Person)-[:ASSIGNED_TO]->(t:Task) RETURN p.name, t.description")
        while edges_ass.has_next():
            row = edges_ass.get_next()
            if G.has_node(row[0]) and G.has_node(row[1]): G.add_edge(row[0], row[1])
            
        # Person -> Topic
        edges_prop = conn.execute("MATCH (p:Person)-[:PROPOSED]->(t:Topic) RETURN p.name, t.title")
        while edges_prop.has_next():
            row = edges_prop.get_next()
            if G.has_node(row[0]) and G.has_node(row[1]): G.add_edge(row[0], row[1])

        # 그래프 그리기
        plt.figure(figsize=(10, 6))
        pos = nx.spring_layout(G, k=0.8)
        node_colors = [nx.get_node_attributes(G, 'color').get(n, '#bdc3c7') for n in G.nodes()]
        
        nx.draw(G, pos, with_labels=True, labels=labels, node_color=node_colors, 
                node_size=1500, font_size=10, font_weight="bold", 
                edge_color="gray", alpha=0.9, 
                font_family=plt.rcParams['font.family'][0])
        
        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches='tight')
        plt.close()
        buf.seek(0)
        
        # 스테가노그래피
        image = Image.open(buf)
        metadata = PngInfo()
        metadata.add_text("speaknode_data", json.dumps(analysis_json, ensure_ascii=False))
        
        final_buf = io.BytesIO()
        image.save(final_buf, "PNG", pnginfo=metadata)
        final_buf.seek(0)
        return final_buf

    except Exception as e:
        st.error(f"이미지 생성 실패: {e}")
        return None
    finally:
        try:
            if conn is not None and hasattr(conn, "close"):
                conn.close()
            if db is not None and hasattr(db, "close"):
                db.close()
        except Exception:
            pass

def render_import_card_ui(share_manager):
    st.divider()
    st.subheader("📥 지식 그래프 불러오기 (DB 복원)")
    import_file = st.file_uploader("SpeakNode 그래프 이미지(PNG)를 업로드하세요", type=["png"], key="import_card")
    
    if import_file:
        temp_path = f"temp_import_{import_file.name}"
        with open(temp_path, "wb") as f:
            f.write(import_file.getbuffer())
        
        data = share_manager.load_data_from_image(temp_path)
        if os.path.exists(temp_path): os.remove(temp_path)
            
        if data:
            st.success("✅ 이미지에서 데이터를 찾았습니다!")
            return data
        else:
            st.error("❌ 데이터가 없는 이미지입니다.")
            return None
    return None
