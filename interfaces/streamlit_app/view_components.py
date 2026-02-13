import streamlit as st
import os
import base64
import zlib
from pyvis.network import Network
import streamlit.components.v1 as components
import networkx as nx
import matplotlib.pyplot as plt
from PIL import Image
from PIL.PngImagePlugin import PngInfo
import io
import json
from core.config import SpeakNodeConfig
from core.db.kuzu_manager import (
    KuzuManager,
    decode_scoped_value,
    extract_scope_from_value,
)
from core.utils import normalize_task_status, TASK_STATUS_OPTIONS

_config = SpeakNodeConfig()


def _encode_payload_for_png(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    compressed = zlib.compress(raw, level=9)
    return base64.b64encode(compressed).decode("ascii")


def _format_scoped_label(raw_value: str) -> str:
    plain = decode_scoped_value(raw_value)
    meeting_scope = extract_scope_from_value(raw_value)
    if meeting_scope:
        return f"{plain} ({meeting_scope})"
    return plain


def set_korean_font():
    """OS에 따른 한글 폰트 설정"""
    try:
        if os.name == "posix":
            plt.rcParams["font.family"] = "NanumGothic"
        else:
            plt.rcParams["font.family"] = "Malgun Gothic"
        plt.rcParams["axes.unicode_minus"] = False
    except Exception as e:
        logger.debug("한글 폰트 설정 건너뜀: %s", e)

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
    try:
        with KuzuManager(db_path=db_path, config=_config) as manager:
            net = Network(height="500px", width="100%", bgcolor="#ffffff", font_color="#333333")

            for person_name, person_role in manager.execute_cypher("MATCH (p:Person) RETURN p.name, p.role"):
                net.add_node(
                    f"person::{person_name}",
                    label=f"{person_name}\n({person_role or 'Member'})",
                    color="#2ecc71",
                    title=person_role or "Member",
                )
            for (title,) in manager.execute_cypher("MATCH (t:Topic) RETURN t.title"):
                net.add_node(
                    f"topic::{title}",
                    label=decode_scoped_value(title),
                    color="#9b59b6",
                    shape="box",
                    title=_format_scoped_label(title),
                )
            for (desc,) in manager.execute_cypher("MATCH (d:Decision) RETURN d.description"):
                net.add_node(
                    f"decision::{desc}",
                    label=decode_scoped_value(desc),
                    color="#f1c40f",
                    shape="triangle",
                    title=_format_scoped_label(desc),
                )
            for (desc,) in manager.execute_cypher("MATCH (t:Task) RETURN t.description"):
                net.add_node(
                    f"task::{desc}",
                    label=decode_scoped_value(desc),
                    color="#3498db",
                    shape="dot",
                    title=_format_scoped_label(desc),
                )

            for topic, decision in manager.execute_cypher(
                "MATCH (t:Topic)-[:RESULTED_IN]->(d:Decision) RETURN t.title, d.description",
            ):
                net.add_edge(f"topic::{topic}", f"decision::{decision}", label="RESULTED_IN")
            for person, task in manager.execute_cypher(
                "MATCH (p:Person)-[:ASSIGNED_TO]->(t:Task) RETURN p.name, t.description",
            ):
                net.add_edge(f"person::{person}", f"task::{task}", label="ASSIGNED_TO")
            for person, topic in manager.execute_cypher(
                "MATCH (p:Person)-[:PROPOSED]->(t:Topic) RETURN p.name, t.title",
            ):
                net.add_edge(f"person::{person}", f"topic::{topic}", label="PROPOSED")

            if not net.nodes:
                st.info("그래프에 표시할 노드가 아직 없습니다.")
                return

            net.toggle_physics(True)
            components.html(net.generate_html(notebook=False), height=550)
    except Exception as e:
        st.error(f"그래프 렌더링 오류: {e}")

def render_graph_editor(db_path):
    st.subheader("✏️ Graph Node Editor")
    st.caption("노드 속성 수정 시 즉시 현재 채팅 DB에 반영됩니다. (기본키 변경은 제외)")

    entity_type = st.selectbox(
        "수정할 노드 유형",
        options=["Topic", "Task", "Person", "Meeting"],
        key="graph_editor_entity_type",
    )

    try:
        with KuzuManager(db_path=db_path, config=_config) as manager:

            if entity_type == "Topic":
                rows = manager.execute_cypher("MATCH (t:Topic) RETURN t.title, t.summary ORDER BY t.title")
                if not rows:
                    st.info("수정할 Topic이 없습니다.")
                    return
                topic_map = {r[0]: (r[1] or "") for r in rows}
                selected = st.selectbox(
                    "Topic 선택",
                    list(topic_map.keys()),
                    key="editor_topic_target",
                    format_func=_format_scoped_label,
                )
                summary_key = f"editor_topic_summary::{selected}"
                new_summary = st.text_area(
                    "요약(summary)",
                    value=topic_map[selected],
                    key=summary_key,
                )
                if st.button("Topic 저장", key="editor_topic_save"):
                    manager.execute_cypher(
                        "MATCH (t:Topic {title: $title}) SET t.summary = $summary",
                        {"title": selected, "summary": new_summary.strip()},
                    )
                    st.success("Topic 요약이 업데이트되었습니다.")
                    st.rerun()

            elif entity_type == "Task":
                rows = manager.execute_cypher(
                    "MATCH (t:Task) OPTIONAL MATCH (p:Person)-[:ASSIGNED_TO]->(t) "
                    "RETURN t.description, t.deadline, t.status, p.name ORDER BY t.description",
                )
                if not rows:
                    st.info("수정할 Task가 없습니다.")
                    return
                task_map = {
                    r[0]: {
                        "deadline": r[1] or "",
                        "status": normalize_task_status(r[2]),
                        "assignee": r[3] or "",
                    }
                    for r in rows
                }
                selected = st.selectbox(
                    "Task 선택",
                    list(task_map.keys()),
                    key="editor_task_target",
                    format_func=_format_scoped_label,
                )
                deadline_key = f"editor_task_deadline::{selected}"
                status_key = f"editor_task_status::{selected}"
                assignee_key = f"editor_task_assignee::{selected}"
                deadline = st.text_input("마감(deadline)", value=task_map[selected]["deadline"], key=deadline_key)
                status = st.selectbox(
                    "상태(status)",
                    options=TASK_STATUS_OPTIONS,
                    index=TASK_STATUS_OPTIONS.index(task_map[selected]["status"]),
                    key=status_key,
                )
                assignee = st.text_input("담당자(assignee)", value=task_map[selected]["assignee"], key=assignee_key)
                if st.button("Task 저장", key="editor_task_save"):
                    manager.execute_cypher(
                        "MATCH (t:Task {description: $desc}) SET t.deadline = $due, t.status = $status",
                        {"desc": selected, "due": deadline.strip() or "TBD", "status": status},
                    )
                    manager.execute_cypher(
                        "MATCH (:Person)-[r:ASSIGNED_TO]->(t:Task {description: $desc}) DELETE r",
                        {"desc": selected},
                    )
                    if assignee.strip():
                        manager.execute_cypher(
                            "MERGE (p:Person {name: $name}) ON CREATE SET p.role = 'Member'",
                            {"name": assignee.strip()},
                        )
                        manager.execute_cypher(
                            "MATCH (p:Person {name: $name}), (t:Task {description: $desc}) "
                            "MERGE (p)-[:ASSIGNED_TO]->(t)",
                            {"name": assignee.strip(), "desc": selected},
                        )
                    st.success("Task 정보가 업데이트되었습니다.")
                    st.rerun()

            elif entity_type == "Person":
                rows = manager.execute_cypher("MATCH (p:Person) RETURN p.name, p.role ORDER BY p.name")
                if not rows:
                    st.info("수정할 Person이 없습니다.")
                    return
                person_map = {r[0]: (r[1] or "Member") for r in rows}
                selected = st.selectbox("Person 선택", list(person_map.keys()), key="editor_person_target")
                role_key = f"editor_person_role::{selected}"
                role = st.text_input("역할(role)", value=person_map[selected], key=role_key)
                if st.button("Person 저장", key="editor_person_save"):
                    manager.execute_cypher(
                        "MATCH (p:Person {name: $name}) SET p.role = $role",
                        {"name": selected, "role": role.strip() or "Member"},
                    )
                    st.success("Person 역할이 업데이트되었습니다.")
                    st.rerun()

            elif entity_type == "Meeting":
                rows = manager.execute_cypher("MATCH (m:Meeting) RETURN m.id, m.title, m.date, m.source_file ORDER BY m.date DESC")
                if not rows:
                    st.info("수정할 Meeting이 없습니다.")
                    return
                meeting_map = {
                    r[0]: {"title": r[1] or "", "date": r[2] or "", "source_file": r[3] or ""}
                    for r in rows
                }
                selected = st.selectbox(
                    "Meeting 선택",
                    options=list(meeting_map.keys()),
                    format_func=lambda x: f"{x} | {meeting_map[x]['title']}",
                    key="editor_meeting_target",
                )
                title_key = f"editor_meeting_title::{selected}"
                date_key = f"editor_meeting_date::{selected}"
                source_key = f"editor_meeting_source::{selected}"
                title = st.text_input("제목(title)", value=meeting_map[selected]["title"], key=title_key)
                date = st.text_input("날짜(date)", value=meeting_map[selected]["date"], key=date_key)
                source_file = st.text_input("원본 파일(source_file)", value=meeting_map[selected]["source_file"], key=source_key)
                if st.button("Meeting 저장", key="editor_meeting_save"):
                    manager.execute_cypher(
                        "MATCH (m:Meeting {id: $id}) SET m.title = $title, m.date = $date, m.source_file = $src",
                        {"id": selected, "title": title.strip(), "date": date.strip(), "src": source_file.strip()},
                    )
                    st.success("Meeting 정보가 업데이트되었습니다.")
                    st.rerun()

    except Exception as e:
        st.error(f"그래프 편집기 오류: {e}")

def generate_static_graph_image(db_path, analysis_json, include_embeddings=False):
    """DB 그래프를 PNG로 렌더링하고 메타데이터에 공유 페이로드를 포함합니다."""
    set_korean_font()
    try:
        with KuzuManager(db_path=db_path, config=_config) as manager:
            G = nx.DiGraph()
            labels = {}

            for (name,) in manager.execute_cypher("MATCH (p:Person) RETURN p.name"):
                G.add_node(name, color="#2ecc71")
                labels[name] = name

            for (title,) in manager.execute_cypher("MATCH (t:Topic) RETURN t.title"):
                G.add_node(title, color="#9b59b6")
                labels[title] = decode_scoped_value(title)

            for (desc,) in manager.execute_cypher("MATCH (d:Decision) RETURN d.description"):
                plain = decode_scoped_value(desc)
                label = (plain[:10] + "..") if len(plain) > 10 else plain
                G.add_node(desc, color="#f1c40f")
                labels[desc] = label

            for (desc,) in manager.execute_cypher("MATCH (t:Task) RETURN t.description"):
                plain = decode_scoped_value(desc)
                label = (plain[:10] + "..") if len(plain) > 10 else plain
                G.add_node(desc, color="#3498db")
                labels[desc] = label

            for src, dst in manager.execute_cypher(
                "MATCH (t:Topic)-[:RESULTED_IN]->(d:Decision) RETURN t.title, d.description"
            ):
                if G.has_node(src) and G.has_node(dst):
                    G.add_edge(src, dst)

            for src, dst in manager.execute_cypher(
                "MATCH (p:Person)-[:ASSIGNED_TO]->(t:Task) RETURN p.name, t.description"
            ):
                if G.has_node(src) and G.has_node(dst):
                    G.add_edge(src, dst)

            for src, dst in manager.execute_cypher(
                "MATCH (p:Person)-[:PROPOSED]->(t:Topic) RETURN p.name, t.title"
            ):
                if G.has_node(src) and G.has_node(dst):
                    G.add_edge(src, dst)

            # 같은 Manager 인스턴스로 graph_dump도 추출 (이중 DB 인스턴스 방지)
            graph_dump = manager.export_graph_dump(include_embeddings=include_embeddings)

        # --- 이미지 렌더링 (DB 연결 해제 후 수행) ---
        plt.figure(figsize=(10, 6))
        pos = nx.spring_layout(G, k=0.8)
        node_colors = [nx.get_node_attributes(G, "color").get(n, "#bdc3c7") for n in G.nodes()]

        nx.draw(
            G,
            pos,
            with_labels=True,
            labels=labels,
            node_color=node_colors,
            node_size=1500,
            font_size=10,
            font_weight="bold",
            edge_color="gray",
            alpha=0.9,
            font_family=plt.rcParams["font.family"][0],
        )

        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight")
        plt.close()
        buf.seek(0)

        image = Image.open(buf)
        metadata = PngInfo()
        payload = {
            "format": "speaknode_graph_bundle_v1",
            "analysis_result": analysis_json,
            "graph_dump": graph_dump,
            "include_embeddings": bool(include_embeddings),
        }
        metadata.add_text("speaknode_data_zlib_b64", _encode_payload_for_png(payload))

        final_buf = io.BytesIO()
        image.save(final_buf, "PNG", pnginfo=metadata)
        final_buf.seek(0)
        return final_buf

    except Exception as e:
        st.error(f"이미지 생성 실패: {e}")
        return None

def render_import_card_ui(share_manager):
    st.divider()
    st.subheader("📥 지식 그래프 불러오기 (DB 복원)")
    import_file = st.file_uploader("SpeakNode 그래프 이미지(PNG)를 업로드하세요", type=["png"], key="import_card")
    
    if import_file:
        # 안전한 임시 파일명 — path traversal 방지
        safe_name = os.path.basename(import_file.name)
        temp_path = f"temp_import_{safe_name}"
        try:
            with open(temp_path, "wb") as f:
                f.write(import_file.getbuffer())
            data = share_manager.load_data_from_image(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        if data:
            st.success("✅ 이미지에서 데이터를 찾았습니다!")
            return data
        else:
            st.error("❌ 데이터가 없는 이미지입니다.")
            return None
    return None
