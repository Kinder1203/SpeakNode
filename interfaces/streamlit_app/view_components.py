import io
import json
import logging
import os
import base64
import zlib

import matplotlib.pyplot as plt
import networkx as nx
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from pyvis.network import Network

from core.config import SpeakNodeConfig
from core.db.kuzu_manager import KuzuManager
from core.utils import normalize_task_status, TASK_STATUS_OPTIONS

logger = logging.getLogger(__name__)
_config = SpeakNodeConfig()


def _encode_payload_for_png(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    compressed = zlib.compress(raw, level=9)
    return base64.b64encode(compressed).decode("ascii")


def set_korean_font():
    """Configure matplotlib for CJK font rendering."""
    try:
        if os.name == "posix":
            plt.rcParams["font.family"] = "NanumGothic"
        else:
            plt.rcParams["font.family"] = "Malgun Gothic"
        plt.rcParams["axes.unicode_minus"] = False
    except Exception as e:
        logger.debug("CJK font setup skipped: %s", e)

def render_header():
    st.title("SpeakNode: Intelligent Meeting Analyst")
    st.markdown("**Local AI-powered meeting knowledge system** &nbsp; · &nbsp; 🛠️ *Developer Debug Dashboard*")
    st.divider()

def render_sidebar():
    with st.sidebar:
        st.header("Workspace")
        return st.file_uploader("Audio file (MP3, WAV, M4A)", type=["mp3", "wav", "m4a"])

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

    # Entity / Relation cards
    entities = result.get('entities', [])
    relations = result.get('relations', [])
    if entities or relations:
        st.divider()
        ec1, ec2 = st.columns(2)
        with ec1:
            st.subheader("🔗 핵심 엔티티")
            for e in entities:
                etype = e.get('entity_type', '')
                desc = e.get('description', '')
                label = f"[{etype}] " if etype else ""
                st.markdown(f"- {label}**{e.get('name', '')}**: {desc}")
        with ec2:
            st.subheader("↔️ 관계")
            for r in relations:
                st.markdown(f"- {r.get('source', '')} → _{r.get('relation_type', '')}_ → {r.get('target', '')}")

def render_graph_view(db_path):
    st.subheader("Knowledge Graph Explorer")
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
                    label=title,
                    color="#9b59b6",
                    shape="box",
                    title=title,
                )
            for (desc,) in manager.execute_cypher("MATCH (d:Decision) RETURN d.description"):
                net.add_node(
                    f"decision::{desc}",
                    label=desc,
                    color="#f1c40f",
                    shape="triangle",
                    title=desc,
                )
            for (desc,) in manager.execute_cypher("MATCH (t:Task) RETURN t.description"):
                net.add_node(
                    f"task::{desc}",
                    label=desc,
                    color="#3498db",
                    shape="dot",
                    title=desc,
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

            # Entity nodes and edges (graceful fallback for old DBs)
            try:
                for name, etype, desc in manager.execute_cypher("MATCH (e:Entity) RETURN e.name, e.entity_type, e.description"):
                    net.add_node(
                        f"entity::{name}",
                        label=f"{name}\n[{etype or 'concept'}]",
                        color="#e67e22",
                        shape="diamond",
                        title=f"{etype}: {desc or name}",
                    )
                for src, rtype, tgt in manager.execute_cypher(
                    "MATCH (a:Entity)-[r:RELATED_TO]->(b:Entity) RETURN a.name, r.relation_type, b.name"
                ):
                    net.add_edge(f"entity::{src}", f"entity::{tgt}", label=rtype or "RELATED_TO")
                for topic, entity in manager.execute_cypher(
                    "MATCH (t:Topic)-[:MENTIONS]->(e:Entity) RETURN t.title, e.name"
                ):
                    net.add_edge(f"topic::{topic}", f"entity::{entity}", label="MENTIONS")
            except Exception:
                pass  # Old DB without Entity table

            if not net.nodes:
                st.info("No nodes to display yet.")
                return

            net.toggle_physics(True)
            components.html(net.generate_html(notebook=False), height=550)
    except Exception as e:
        st.error(f"Graph rendering error: {e}")

def render_graph_editor(db_path):
    st.subheader("Graph Node Editor")
    st.caption("Changes are immediately persisted to the active chat DB. Primary keys cannot be changed.")

    entity_type = st.selectbox(
        "Node type",
        options=["Topic", "Task", "Person", "Meeting", "Entity"],
        key="graph_editor_entity_type",
    )

    try:
        with KuzuManager(db_path=db_path, config=_config) as manager:

            if entity_type == "Topic":
                rows = manager.execute_cypher("MATCH (t:Topic) RETURN t.title, t.summary ORDER BY t.title")
                if not rows:
                    st.info("No Topics to edit.")
                    return
                topic_map = {r[0]: (r[1] or "") for r in rows}
                selected = st.selectbox(
                    "Select Topic",
                    list(topic_map.keys()),
                    key="editor_topic_target",
                )
                summary_key = f"editor_topic_summary::{selected}"
                new_summary = st.text_area(
                    "Summary",
                    value=topic_map[selected],
                    key=summary_key,
                )
                if st.button("Save Topic", key="editor_topic_save"):
                    manager.execute_cypher(
                        "MATCH (t:Topic {title: $title}) SET t.summary = $summary",
                        {"title": selected, "summary": new_summary.strip()},
                    )
                    st.success("Topic updated.")
                    st.rerun()

            elif entity_type == "Task":
                rows = manager.execute_cypher(
                    "MATCH (t:Task) OPTIONAL MATCH (p:Person)-[:ASSIGNED_TO]->(t) "
                    "RETURN t.description, t.deadline, t.status, p.name ORDER BY t.description",
                )
                if not rows:
                    st.info("No Tasks to edit.")
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
                    "Select Task",
                    list(task_map.keys()),
                    key="editor_task_target",
                )
                deadline_key = f"editor_task_deadline::{selected}"
                status_key = f"editor_task_status::{selected}"
                assignee_key = f"editor_task_assignee::{selected}"
                deadline = st.text_input("Deadline", value=task_map[selected]["deadline"], key=deadline_key)
                status = st.selectbox(
                    "Status",
                    options=TASK_STATUS_OPTIONS,
                    index=TASK_STATUS_OPTIONS.index(task_map[selected]["status"]),
                    key=status_key,
                )
                assignee = st.text_input("Assignee", value=task_map[selected]["assignee"], key=assignee_key)
                if st.button("Save Task", key="editor_task_save"):
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
                    st.success("Task updated.")
                    st.rerun()

            elif entity_type == "Person":
                rows = manager.execute_cypher("MATCH (p:Person) RETURN p.name, p.role ORDER BY p.name")
                if not rows:
                    st.info("No People to edit.")
                    return
                person_map = {r[0]: (r[1] or "Member") for r in rows}
                selected = st.selectbox("Select Person", list(person_map.keys()), key="editor_person_target")
                role_key = f"editor_person_role::{selected}"
                role = st.text_input("Role", value=person_map[selected], key=role_key)
                if st.button("Save Person", key="editor_person_save"):
                    manager.execute_cypher(
                        "MATCH (p:Person {name: $name}) SET p.role = $role",
                        {"name": selected, "role": role.strip() or "Member"},
                    )
                    st.success("Person updated.")
                    st.rerun()

            elif entity_type == "Entity":
                try:
                    rows = manager.execute_cypher("MATCH (e:Entity) RETURN e.name, e.entity_type, e.description ORDER BY e.name")
                except Exception:
                    rows = []
                if not rows:
                    st.info("No Entities to edit.")
                    return
                entity_map = {
                    r[0]: {"entity_type": r[1] or "concept", "description": r[2] or ""}
                    for r in rows
                }
                selected = st.selectbox(
                    "Select Entity",
                    list(entity_map.keys()),
                    key="editor_entity_target",
                )
                desc_key = f"editor_entity_desc::{selected}"
                new_desc = st.text_area(
                    "Description",
                    value=entity_map[selected]["description"],
                    key=desc_key,
                )
                if st.button("Save Entity", key="editor_entity_save"):
                    manager.execute_cypher(
                        "MATCH (e:Entity {name: $name}) SET e.description = $desc",
                        {"name": selected, "desc": new_desc.strip()},
                    )
                    st.success("Entity updated.")
                    st.rerun()

            elif entity_type == "Meeting":
                rows = manager.execute_cypher("MATCH (m:Meeting) RETURN m.id, m.title, m.date, m.source_file ORDER BY m.date DESC")
                if not rows:
                    st.info("No Meetings to edit.")
                    return
                meeting_map = {
                    r[0]: {"title": r[1] or "", "date": r[2] or "", "source_file": r[3] or ""}
                    for r in rows
                }
                selected = st.selectbox(
                    "Select Meeting",
                    options=list(meeting_map.keys()),
                    format_func=lambda x: f"{x} | {meeting_map[x]['title']}",
                    key="editor_meeting_target",
                )
                title_key = f"editor_meeting_title::{selected}"
                date_key = f"editor_meeting_date::{selected}"
                source_key = f"editor_meeting_source::{selected}"
                title = st.text_input("Title", value=meeting_map[selected]["title"], key=title_key)
                date = st.text_input("Date", value=meeting_map[selected]["date"], key=date_key)
                source_file = st.text_input("Source file", value=meeting_map[selected]["source_file"], key=source_key)
                if st.button("Save Meeting", key="editor_meeting_save"):
                    manager.execute_cypher(
                        "MATCH (m:Meeting {id: $id}) SET m.title = $title, m.date = $date, m.source_file = $src",
                        {"id": selected, "title": title.strip(), "date": date.strip(), "src": source_file.strip()},
                    )
                    st.success("Meeting updated.")
                    st.rerun()

    except Exception as e:
        st.error(f"Graph editor error: {e}")

def generate_static_graph_image(db_path, analysis_json, include_embeddings=False):
    """Render DB graph to PNG with embedded share payload in metadata."""
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
                labels[title] = title

            for (desc,) in manager.execute_cypher("MATCH (d:Decision) RETURN d.description"):
                label = (desc[:10] + "..") if len(desc) > 10 else desc
                G.add_node(desc, color="#f1c40f")
                labels[desc] = label

            for (desc,) in manager.execute_cypher("MATCH (t:Task) RETURN t.description"):
                label = (desc[:10] + "..") if len(desc) > 10 else desc
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

            # Entity nodes and edges for static image (graceful fallback)
            try:
                for name, etype, desc in manager.execute_cypher("MATCH (e:Entity) RETURN e.name, e.entity_type, e.description"):
                    label = (name[:12] + "..") if len(name) > 12 else name
                    G.add_node(name, color="#e67e22")
                    labels[name] = label
                for src, rtype, tgt in manager.execute_cypher(
                    "MATCH (a:Entity)-[r:RELATED_TO]->(b:Entity) RETURN a.name, r.relation_type, b.name"
                ):
                    if G.has_node(src) and G.has_node(tgt):
                        G.add_edge(src, tgt)
                for topic, entity in manager.execute_cypher(
                    "MATCH (t:Topic)-[:MENTIONS]->(e:Entity) RETURN t.title, e.name"
                ):
                    if G.has_node(topic) and G.has_node(entity):
                        G.add_edge(topic, entity)
            except Exception:
                pass  # Old DB without Entity table

            graph_dump = manager.export_graph_dump(include_embeddings=include_embeddings)

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
        st.error(f"Image generation failed: {e}")
        return None

def render_import_card_ui(share_manager):
    st.divider()
    st.subheader("Import Knowledge Graph")
    import_file = st.file_uploader("Upload a SpeakNode graph image (PNG)", type=["png"], key="import_card")
    
    if import_file:
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
            st.success("Data extracted from image.")
            return data
        else:
            st.error("No SpeakNode data found in this image.")
            return None
    return None
