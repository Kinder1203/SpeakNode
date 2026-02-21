import io
import json
import logging
import os
import base64
import tempfile
import zlib

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from core.config import SpeakNodeConfig
from core.db.kuzu_manager import KuzuManager
from core.utils import normalize_task_status, TASK_STATUS_OPTIONS

logger = logging.getLogger(__name__)
_config = SpeakNodeConfig()

# ── Node style constants matching docs/index.html ─────────────────────────────
_NODE_COLORS = {
    "meeting":   "#60a5fa",
    "person":    "#a855f7",
    "topic":     "#22c55e",
    "task":      "#f59e0b",
    "decision":  "#f472b6",
    "entity":    "#ec4899",
    "utterance": "#06b6d4",
}
_NODE_BORDER = {
    "meeting":   "#3b82f6",
    "person":    "#9333ea",
    "topic":     "#16a34a",
    "task":      "#d97706",
    "decision":  "#db2777",
    "entity":    "#be185d",
    "utterance": "#0891b2",
}
_NODE_SIZE = {
    "meeting": 28, "person": 20, "topic": 18,
    "task": 16, "decision": 16, "entity": 14, "utterance": 10,
}
_NODE_EMOJI = {
    "meeting": "📅", "person": "👤", "topic": "💡",
    "task": "✅", "decision": "⚖️", "entity": "🔗", "utterance": "💬",
}


def _encode_payload_for_png(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    compressed = zlib.compress(raw, level=9)
    return base64.b64encode(compressed).decode("ascii")


def _set_korean_font():
    """Configure matplotlib for CJK font rendering."""
    import matplotlib.pyplot as plt
    try:
        plt.rcParams["font.family"] = "NanumGothic" if os.name == "posix" else "Malgun Gothic"
        plt.rcParams["axes.unicode_minus"] = False
    except Exception as e:
        logger.debug("CJK font setup skipped: %s", e)


# ── Header ────────────────────────────────────────────────────────────────────

def render_header():
    st.markdown(
        """
        <div style="padding:0.25rem 0 0.75rem 0;">
          <h1 style="margin:0;font-size:1.9rem;font-weight:700;
                     background:linear-gradient(90deg,#60a5fa,#a855f7);
                     -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
            🎙️ SpeakNode
          </h1>
          <p style="margin:0.2rem 0 0 0;color:#94a3b8;font-size:0.88rem;">
            AI 회의 지식 그래프 시스템 &nbsp;·&nbsp; Local-First
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Welcome / Onboarding ──────────────────────────────────────────────────────

def render_welcome_page():
    st.markdown(
        """
        <div style="text-align:center;padding:56px 20px 32px 20px;">
          <div style="font-size:3.5rem;margin-bottom:0.8rem;">🎙️</div>
          <h2 style="color:#e2e8f0;font-weight:600;margin:0 0 0.5rem 0;">
            회의를 지식으로 변환하세요
          </h2>
          <p style="color:#94a3b8;font-size:0.97rem;max-width:460px;
                    margin:0 auto 2rem auto;line-height:1.7;">
            MP3 / WAV / M4A 파일을 업로드하면 AI가 자동으로<br>
            주제 · 할 일 · 결정사항 · 지식 그래프를 추출합니다.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    col1, col2, col3 = st.columns(3)
    cards = [
        ("🎤", "음성 인식 (STT)", "Faster-Whisper 로 음성을 텍스트로"),
        ("🧠", "AI 지식 추출", "Ollama LLM 이 주제·할일·엔티티 추출"),
        ("💬", "대화형 AI Agent", "그래프 DB 기반 회의 Q&A"),
    ]
    for col, (icon, title, desc) in zip([col1, col2, col3], cards):
        with col:
            st.markdown(
                f"""
                <div style="background:#1e293b;border-radius:12px;padding:22px 16px;
                            text-align:center;border:1px solid #334155;min-height:130px;">
                  <div style="font-size:2rem;">{icon}</div>
                  <div style="font-weight:600;color:#e2e8f0;margin:8px 0 4px 0;font-size:0.9rem;">{title}</div>
                  <div style="color:#64748b;font-size:0.8rem;">{desc}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ── Analysis Cards ────────────────────────────────────────────────────────────

def render_sidebar():
    with st.sidebar:
        st.header("Workspace")
        return st.file_uploader("Audio file (MP3, WAV, M4A)", type=["mp3", "wav", "m4a"])

def display_analysis_cards(result):
    if not result:
        return
    topics    = result.get("topics", [])
    decisions = result.get("decisions", [])
    tasks     = result.get("tasks", [])
    entities  = result.get("entities", [])
    relations = result.get("relations", [])
    people    = result.get("people", [])

    # Summary metric row
    m1, m2, m3, m4, m5 = st.columns(5)
    for col, (label, val) in zip(
        [m1, m2, m3, m4, m5],
        [("💡 주제", len(topics)), ("⚖️ 결정", len(decisions)),
         ("📋 할 일", len(tasks)), ("👤 인물", len(people)),
         ("🔗 엔티티", len(entities))],
    ):
        col.metric(label, val)

    st.divider()
    col_left, col_right = st.columns([1, 1])

    with col_left:
        if topics:
            st.markdown("#### 💡 주제")
            for t in topics:
                with st.expander(f"**{t.get('title', '')}**", expanded=False):
                    st.write(t.get("summary", "요약 없음"))
                    if t.get("proposer") and t["proposer"] != "Unknown":
                        st.caption(f"제안자: {t['proposer']}")

        if decisions:
            st.markdown("#### ⚖️ 결정사항")
            for d in decisions:
                st.success(d.get("description", ""))

    with col_right:
        if tasks:
            st.markdown("#### 📋 할 일 목록")
            for task in tasks:
                status   = task.get("status", "pending")
                assignee = task.get("assignee", "")
                deadline = task.get("deadline", "")
                badge = {
                    "done": "#22c55e", "in_progress": "#f59e0b",
                    "blocked": "#ef4444", "pending": "#64748b",
                }.get(status, "#64748b")
                meta_parts = []
                if assignee and assignee != "Unassigned":
                    meta_parts.append(f"담당: {assignee}")
                if deadline and deadline != "TBD":
                    meta_parts.append(f"마감: {deadline}")
                meta = " &nbsp;|&nbsp; ".join(meta_parts)
                st.markdown(
                    f"""
                    <div style="background:#1e293b;border-radius:8px;padding:10px 14px;
                                margin-bottom:8px;border-left:3px solid {badge};">
                      <div style="color:#e2e8f0;font-size:0.88rem;">{task.get("description","")}</div>
                      <div style="color:#64748b;font-size:0.77rem;margin-top:3px;">{meta}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        if entities or relations:
            st.markdown("#### 🔗 핵심 엔티티 & 관계")
            if entities:
                with st.expander(f"엔티티 {len(entities)}건", expanded=False):
                    for e in entities:
                        etype = e.get("entity_type", "")
                        prefix = f"[{etype}] " if etype else ""
                        st.markdown(f"- {prefix}**{e.get('name','')}**: {e.get('description','')}")
            if relations:
                with st.expander(f"관계 {len(relations)}건", expanded=False):
                    for r in relations:
                        st.markdown(
                            f"- `{r.get('source','')}` → **{r.get('relation_type','')}** → `{r.get('target','')}`"
                        )





# ── Knowledge Graph (vis-network) ────────────────────────────────────────────

def _build_vis_html(nodes_json: str, edges_json: str, height: int = 640) -> str:
    """Return a self-contained vis-network HTML page matching docs/index.html style."""
    # Use plain string concatenation to avoid f-string conflicts with JS {} syntax.
    toolbar_html = (
        "<div id='toolbar'>"
        "<label><input type='checkbox' id='toggle-utt'> 💬 발언 노드 표시</label>"
        "<div id='legend'>"
        "<div class='li'><div class='ld' style='background:#60a5fa'></div>회의</div>"
        "<div class='li'><div class='ld' style='background:#a855f7'></div>인물</div>"
        "<div class='li'><div class='ld' style='background:#22c55e'></div>주제</div>"
        "<div class='li'><div class='ld' style='background:#f59e0b'></div>할일</div>"
        "<div class='li'><div class='ld' style='background:#f472b6'></div>결정</div>"
        "<div class='li'><div class='ld' style='background:#ec4899'></div>엔티티</div>"
        "</div></div>"
    )
    css = (
        "<style>"
        "*{box-sizing:border-box;margin:0;padding:0;}"
        "body{background:#0f172a;font-family:'Malgun Gothic','Apple SD Gothic Neo',sans-serif;"
        "height:" + str(height) + "px;overflow:hidden;}"
        "#toolbar{display:flex;align-items:center;gap:14px;padding:7px 14px;"
        "background:#1e293b;border-bottom:1px solid #334155;}"
        "#toolbar label{color:#94a3b8;font-size:0.82rem;display:flex;align-items:center;"
        "gap:6px;cursor:pointer;user-select:none;}"
        "#toolbar input[type=checkbox]{accent-color:#60a5fa;width:14px;height:14px;}"
        "#legend{display:flex;gap:10px;margin-left:auto;flex-wrap:wrap;}"
        ".li{display:flex;align-items:center;gap:4px;font-size:0.75rem;color:#94a3b8;}"
        ".ld{width:10px;height:10px;border-radius:50%;flex-shrink:0;}"
        "#gwrap{display:flex;height:calc(" + str(height) + "px - 41px);}"
        "#network{flex:1;}"
        "#dpanel{width:260px;background:#1e293b;border-left:1px solid #334155;"
        "padding:16px;overflow-y:auto;flex-shrink:0;}"
        "#dtitle{font-size:0.95rem;font-weight:600;color:#e2e8f0;margin-bottom:8px;"
        "min-height:22px;}"
        "#dbody{font-size:0.82rem;color:#94a3b8;line-height:1.7;}"
        ".drow{margin-bottom:6px;word-break:break-word;}"
        ".dkey{color:#60a5fa;font-weight:600;font-size:0.78rem;}"
        "#dhint{color:#475569;font-size:0.82rem;text-align:center;margin-top:40px;}"
        "</style>"
    )
    js_body = (
        "<script>"
        "const RAW_NODES=" + nodes_json + ";"
        "const RAW_EDGES=" + edges_json + ";"
        "function dv(s){if(!s)return '';const i=String(s).indexOf('::');return i>=0?s.slice(i+2):s;}"
        "const nodesDS=new vis.DataSet(RAW_NODES);"
        "const edgesDS=new vis.DataSet(RAW_EDGES);"
        "const container=document.getElementById('network');"
        "const opts={"
        "  physics:{enabled:true,solver:'forceAtlas2Based',"
        "    forceAtlas2Based:{gravitationalConstant:-55,springLength:130,"
        "      springConstant:0.05,damping:0.42},"
        "    stabilization:{iterations:250,updateInterval:25}},"
        "  edges:{color:{color:'#475569',highlight:'#94a3b8'},"
        "    font:{color:'#94a3b8',size:11,align:'middle',strokeWidth:2,strokeColor:'#0f172a'},"
        "    arrows:{to:{enabled:true,scaleFactor:0.55}},"
        "    smooth:{type:'cubicBezier',forceDirection:'none',roundness:0.4}},"
        "  nodes:{font:{color:'#e2e8f0',size:13,strokeWidth:2,strokeColor:'#0f172a'},"
        "    borderWidth:2,shadow:true},"
        "  interaction:{hover:true,tooltipDelay:80},"
        "  layout:{improvedLayout:false}"
        "};"
        "const network=new vis.Network(container,{nodes:nodesDS,edges:edgesDS},opts);"
        # Utterance toggle
        "document.getElementById('toggle-utt').addEventListener('change',function(){"
        "  const show=this.checked;"
        "  const uttIds=RAW_NODES.filter(n=>n._type==='utterance').map(n=>n.id);"
        "  uttIds.forEach(id=>nodesDS.update({id,hidden:!show}));"
        "  const uttEids=RAW_EDGES"
        "    .filter(e=>uttIds.includes(e.from)||uttIds.includes(e.to)).map(e=>e.id);"
        "  uttEids.forEach(id=>edgesDS.update({id,hidden:!show}));"
        "});"
        # Click detail panel
        "const typeLabel={"
        "  meeting:'📅 회의',person:'👤 인물',topic:'💡 주제',"
        "  task:'✅ 할 일',decision:'⚖️ 결정',entity:'🔗 엔티티',utterance:'💬 발언'"
        "};"
        "network.on('click',function(params){"
        "  const panel=document.getElementById('dbody');"
        "  const title=document.getElementById('dtitle');"
        "  if(!params.nodes.length){"
        "    title.textContent='노드 상세';"
        "    panel.innerHTML='<p id=\"dhint\">노드를 클릭하여<br>상세 정보를 확인하세요</p>';"
        "    return;"
        "  }"
        "  const node=nodesDS.get(params.nodes[0]);"
        "  if(!node)return;"
        "  title.textContent=typeLabel[node._type]||node._type||'노드';"
        "  const data=node._data||{};"
        "  let html='';"
        "  for(const[k,v] of Object.entries(data)){"
        "    if(v!==null&&v!==undefined&&v!==''){"
        "      html+=`<div class=\"drow\"><span class=\"dkey\">${k}</span><br>${dv(String(v))}</div>`;"
        "    }"
        "  }"
        "  panel.innerHTML=html||'<span style=\"color:#475569\">데이터 없음</span>';"
        "});"
        # Double-click zoom
        "network.on('doubleClick',function(params){"
        "  if(params.nodes.length){"
        "    network.focus(params.nodes[0],{scale:1.6,"
        "      animation:{duration:500,easingFunction:'easeInOutQuad'}});"
        "  }"
        "});"
        "</script>"
    )
    return (
        "<!DOCTYPE html><html><head><meta charset='UTF-8'/>"
        "<script src='https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js'>"
        "</script>" + css + "</head><body>"
        + toolbar_html
        + "<div id='gwrap'><div id='network'></div>"
        + "<div id='dpanel'><div id='dtitle'>노드 상세</div>"
        + "<div id='dbody'><p id='dhint'>노드를 클릭하여<br>상세 정보를 확인하세요</p></div>"
        + "</div></div>"
        + js_body
        + "</body></html>"
    )


def render_graph_view(db_path: str):
    st.markdown("#### 🧠 지식 그래프")
    try:
        with KuzuManager(db_path=db_path, config=_config) as mgr:
            vis_nodes: list[dict] = []
            vis_edges: list[dict] = []
            _eid_counter = [0]

            def _eid() -> str:
                _eid_counter[0] += 1
                return f"e{_eid_counter[0]}"

            def _add_node(nid, label, ntype, data, hidden=False):
                vis_nodes.append({
                    "id": nid,
                    "label": label,
                    "color": {
                        "background": _NODE_COLORS[ntype],
                        "border": _NODE_BORDER[ntype],
                        "highlight": {"background": _NODE_COLORS[ntype], "border": "#ffffff"},
                    },
                    "size": _NODE_SIZE[ntype],
                    "_type": ntype,
                    "_data": data,
                    "title": label,
                    "hidden": hidden,
                })

            def _add_edge(frm, to, label="", width=1.2, hidden=False):
                vis_edges.append({
                    "id": _eid(), "from": frm, "to": to,
                    "label": label, "width": width, "hidden": hidden,
                })

            # ── Meeting nodes ─────────────────────────────────────────────────
            for mid, mtitle, mdate, msrc in mgr.execute_cypher(
                "MATCH (m:Meeting) RETURN m.id, m.title, m.date, m.source_file"
            ):
                _add_node(
                    f"meeting::{mid}",
                    f"📅 {mtitle or mid}",
                    "meeting",
                    {"ID": mid, "제목": mtitle, "날짜": mdate, "파일": msrc},
                )

            # ── Person nodes ──────────────────────────────────────────────────
            for pname, prole in mgr.execute_cypher("MATCH (p:Person) RETURN p.name, p.role"):
                _add_node(
                    f"person::{pname}",
                    f"👤 {pname}",
                    "person",
                    {"이름": pname, "역할": prole or "Member"},
                )

            # ── Topic nodes ───────────────────────────────────────────────────
            for ttitle, tsummary in mgr.execute_cypher("MATCH (t:Topic) RETURN t.title, t.summary"):
                _add_node(
                    f"topic::{ttitle}",
                    f"💡 {ttitle}",
                    "topic",
                    {"제목": ttitle, "요약": tsummary or ""},
                )

            # ── Task nodes ────────────────────────────────────────────────────
            for tdesc, tdue, tstatus in mgr.execute_cypher(
                "MATCH (t:Task) RETURN t.description, t.deadline, t.status"
            ):
                lbl = (tdesc[:22] + "…") if tdesc and len(tdesc) > 22 else tdesc
                _add_node(
                    f"task::{tdesc}",
                    f"✅ {lbl}",
                    "task",
                    {"내용": tdesc, "마감": tdue or "TBD", "상태": tstatus or ""},
                )

            # ── Decision nodes ────────────────────────────────────────────────
            for (ddesc,) in mgr.execute_cypher("MATCH (d:Decision) RETURN d.description"):
                lbl = (ddesc[:22] + "…") if ddesc and len(ddesc) > 22 else ddesc
                _add_node(
                    f"decision::{ddesc}",
                    f"⚖️ {lbl}",
                    "decision",
                    {"결정": ddesc},
                )

            # ── Utterance nodes (hidden by default) ───────────────────────────
            for uid, utext, ustart, uend in mgr.execute_cypher(
                "MATCH (u:Utterance) RETURN u.id, u.text, u.startTime, u.endTime LIMIT 200"
            ):
                snippet = (utext[:28] + "…") if utext and len(utext) > 28 else (utext or "")
                _add_node(
                    f"utterance::{uid}",
                    f"💬 {snippet}",
                    "utterance",
                    {"ID": uid, "텍스트": utext, "시작": ustart, "종료": uend},
                    hidden=True,
                )

            # ── Entity nodes ──────────────────────────────────────────────────
            try:
                for ename, etype, edesc in mgr.execute_cypher(
                    "MATCH (e:Entity) RETURN e.name, e.entity_type, e.description"
                ):
                    _add_node(
                        f"entity::{ename}",
                        f"🔗 {ename}",
                        "entity",
                        {"이름": ename, "유형": etype or "concept", "설명": edesc or ""},
                    )
            except Exception:
                pass  # Old DB without Entity table — skip silently

            # ── Edges ─────────────────────────────────────────────────────────
            for topic, decision in mgr.execute_cypher(
                "MATCH (t:Topic)-[:RESULTED_IN]->(d:Decision) RETURN t.title, d.description"
            ):
                _add_edge(f"topic::{topic}", f"decision::{decision}", "RESULTED_IN", 2)

            for person, task in mgr.execute_cypher(
                "MATCH (p:Person)-[:ASSIGNED_TO]->(t:Task) RETURN p.name, t.description"
            ):
                _add_edge(f"person::{person}", f"task::{task}", "담당", 1.5)

            for person, topic in mgr.execute_cypher(
                "MATCH (p:Person)-[:PROPOSED]->(t:Topic) RETURN p.name, t.title"
            ):
                _add_edge(f"person::{person}", f"topic::{topic}", "제안", 1.5)

            for mid, ttitle in mgr.execute_cypher(
                "MATCH (m:Meeting)-[:DISCUSSED]->(t:Topic) RETURN m.id, t.title"
            ):
                _add_edge(f"meeting::{mid}", f"topic::{ttitle}", "DISCUSSED")

            for mid, tdesc in mgr.execute_cypher(
                "MATCH (m:Meeting)-[:HAS_TASK]->(t:Task) RETURN m.id, t.description"
            ):
                _add_edge(f"meeting::{mid}", f"task::{tdesc}", "HAS_TASK")

            for mid, ddesc in mgr.execute_cypher(
                "MATCH (m:Meeting)-[:HAS_DECISION]->(d:Decision) RETURN m.id, d.description"
            ):
                _add_edge(f"meeting::{mid}", f"decision::{ddesc}", "HAS_DECISION")

            # Utterance edges (hidden by default)
            for pname, uid in mgr.execute_cypher(
                "MATCH (p:Person)-[:SPOKE]->(u:Utterance) RETURN p.name, u.id LIMIT 200"
            ):
                _add_edge(f"person::{pname}", f"utterance::{uid}", "SPOKE", hidden=True)

            for mid, uid in mgr.execute_cypher(
                "MATCH (m:Meeting)-[:CONTAINS]->(u:Utterance) RETURN m.id, u.id LIMIT 200"
            ):
                _add_edge(f"meeting::{mid}", f"utterance::{uid}", "CONTAINS", hidden=True)

            # Entity edges
            try:
                for src, rtype, tgt in mgr.execute_cypher(
                    "MATCH (a:Entity)-[r:RELATED_TO]->(b:Entity) RETURN a.name, r.relation_type, b.name"
                ):
                    _add_edge(f"entity::{src}", f"entity::{tgt}", rtype or "RELATED_TO", 1.5)
                for ttitle, ename in mgr.execute_cypher(
                    "MATCH (t:Topic)-[:MENTIONS]->(e:Entity) RETURN t.title, e.name"
                ):
                    _add_edge(f"topic::{ttitle}", f"entity::{ename}", "MENTIONS")
                for mid, ename in mgr.execute_cypher(
                    "MATCH (m:Meeting)-[:HAS_ENTITY]->(e:Entity) RETURN m.id, e.name"
                ):
                    _add_edge(f"meeting::{mid}", f"entity::{ename}", "HAS_ENTITY")
            except Exception:
                pass

        if not vis_nodes:
            st.info("그래프 데이터가 없습니다. 분석 완료 후 다시 확인하세요.")
            return

        nodes_json = json.dumps(vis_nodes, ensure_ascii=False)
        edges_json = json.dumps(vis_edges, ensure_ascii=False)
        html = _build_vis_html(nodes_json, edges_json, height=640)
        components.html(html, height=682, scrolling=False)

    except Exception as e:
        st.error(f"그래프 렌더링 오류: {e}")
        logger.exception("Graph rendering failed")



def render_graph_editor(db_path: str):
    with st.expander("⚙️ 그래프 노드 편집", expanded=False):
        st.caption("변경 사항은 즉시 DB에 반영됩니다. Primary key(이름/제목/내용)는 변경 불가입니다.")

        entity_type = st.selectbox(
            "노드 유형",
            options=["Topic", "Task", "Person", "Meeting", "Entity"],
            key="graph_editor_entity_type",
        )

        try:
            with KuzuManager(db_path=db_path, config=_config) as manager:

                if entity_type == "Topic":
                    rows = manager.execute_cypher(
                        "MATCH (t:Topic) RETURN t.title, t.summary ORDER BY t.title"
                    )
                    if not rows:
                        st.info("편집할 주제가 없습니다.")
                        return
                    topic_map = {r[0]: (r[1] or "") for r in rows}
                    selected = st.selectbox("주제 선택", list(topic_map.keys()), key="editor_topic_target")
                    new_summary = st.text_area(
                        "요약", value=topic_map[selected], key=f"editor_topic_summary::{selected}"
                    )
                    if st.button("저장", key="editor_topic_save"):
                        manager.execute_cypher(
                            "MATCH (t:Topic {title: $title}) SET t.summary = $summary",
                            {"title": selected, "summary": new_summary.strip()},
                        )
                        st.success("주제 업데이트 완료")
                        st.rerun()

                elif entity_type == "Task":
                    rows = manager.execute_cypher(
                        "MATCH (t:Task) OPTIONAL MATCH (p:Person)-[:ASSIGNED_TO]->(t) "
                        "RETURN t.description, t.deadline, t.status, p.name ORDER BY t.description"
                    )
                    if not rows:
                        st.info("편집할 할 일이 없습니다.")
                        return
                    task_map = {
                        r[0]: {
                            "deadline": r[1] or "",
                            "status": normalize_task_status(r[2]),
                            "assignee": r[3] or "",
                        }
                        for r in rows
                    }
                    selected = st.selectbox("할 일 선택", list(task_map.keys()), key="editor_task_target")
                    deadline = st.text_input(
                        "마감일", value=task_map[selected]["deadline"],
                        key=f"editor_task_deadline::{selected}",
                    )
                    status = st.selectbox(
                        "상태", options=TASK_STATUS_OPTIONS,
                        index=TASK_STATUS_OPTIONS.index(task_map[selected]["status"]),
                        key=f"editor_task_status::{selected}",
                    )
                    assignee = st.text_input(
                        "담당자", value=task_map[selected]["assignee"],
                        key=f"editor_task_assignee::{selected}",
                    )
                    if st.button("저장", key="editor_task_save"):
                        manager.execute_cypher(
                            "MATCH (t:Task {description: $desc}) SET t.deadline = $due, t.status = $status",
                            {"desc": selected, "due": deadline.strip() or "TBD", "status": status},
                        )
                        manager.execute_cypher(
                            "MATCH (:Person)-[r:ASSIGNED_TO]->(t:Task {description: $desc}) DELETE r",
                            {"desc": selected},
                        )
                        if assignee.strip():
                            # MERGE then SET — ON CREATE SET is not supported in KuzuDB
                            manager.execute_cypher(
                                "MERGE (p:Person {name: $name})", {"name": assignee.strip()}
                            )
                            manager.execute_cypher(
                                "MATCH (p:Person {name: $name}) SET p.role = 'Member'",
                                {"name": assignee.strip()},
                            )
                            manager.execute_cypher(
                                "MATCH (p:Person {name: $name}), (t:Task {description: $desc}) "
                                "MERGE (p)-[:ASSIGNED_TO]->(t)",
                                {"name": assignee.strip(), "desc": selected},
                            )
                        st.success("할 일 업데이트 완료")
                        st.rerun()

                elif entity_type == "Person":
                    rows = manager.execute_cypher(
                        "MATCH (p:Person) RETURN p.name, p.role ORDER BY p.name"
                    )
                    if not rows:
                        st.info("편집할 인물이 없습니다.")
                        return
                    person_map = {r[0]: (r[1] or "Member") for r in rows}
                    selected = st.selectbox("인물 선택", list(person_map.keys()), key="editor_person_target")
                    role = st.text_input(
                        "역할", value=person_map[selected],
                        key=f"editor_person_role::{selected}",
                    )
                    if st.button("저장", key="editor_person_save"):
                        manager.execute_cypher(
                            "MATCH (p:Person {name: $name}) SET p.role = $role",
                            {"name": selected, "role": role.strip() or "Member"},
                        )
                        st.success("인물 업데이트 완료")
                        st.rerun()

                elif entity_type == "Entity":
                    try:
                        rows = manager.execute_cypher(
                            "MATCH (e:Entity) RETURN e.name, e.entity_type, e.description ORDER BY e.name"
                        )
                    except Exception:
                        rows = []
                    if not rows:
                        st.info("편집할 엔티티가 없습니다.")
                        return
                    entity_map = {
                        r[0]: {"entity_type": r[1] or "concept", "description": r[2] or ""}
                        for r in rows
                    }
                    selected = st.selectbox("엔티티 선택", list(entity_map.keys()), key="editor_entity_target")
                    new_desc = st.text_area(
                        "설명", value=entity_map[selected]["description"],
                        key=f"editor_entity_desc::{selected}",
                    )
                    if st.button("저장", key="editor_entity_save"):
                        manager.execute_cypher(
                            "MATCH (e:Entity {name: $name}) SET e.description = $desc",
                            {"name": selected, "desc": new_desc.strip()},
                        )
                        st.success("엔티티 업데이트 완료")
                        st.rerun()

                elif entity_type == "Meeting":
                    rows = manager.execute_cypher(
                        "MATCH (m:Meeting) RETURN m.id, m.title, m.date, m.source_file ORDER BY m.date DESC"
                    )
                    if not rows:
                        st.info("편집할 회의가 없습니다.")
                        return
                    meeting_map = {
                        r[0]: {"title": r[1] or "", "date": r[2] or "", "source_file": r[3] or ""}
                        for r in rows
                    }
                    selected = st.selectbox(
                        "회의 선택", options=list(meeting_map.keys()),
                        format_func=lambda x: f"{x} | {meeting_map[x]['title']}",
                        key="editor_meeting_target",
                    )
                    title = st.text_input("제목", value=meeting_map[selected]["title"], key=f"editor_meeting_title::{selected}")
                    date  = st.text_input("날짜", value=meeting_map[selected]["date"],  key=f"editor_meeting_date::{selected}")
                    src   = st.text_input("파일명", value=meeting_map[selected]["source_file"], key=f"editor_meeting_source::{selected}")
                    if st.button("저장", key="editor_meeting_save"):
                        manager.execute_cypher(
                            "MATCH (m:Meeting {id: $id}) SET m.title = $title, m.date = $date, m.source_file = $src",
                            {"id": selected, "title": title.strip(), "date": date.strip(), "src": src.strip()},
                        )
                        st.success("회의 업데이트 완료")
                        st.rerun()

        except Exception as e:
            st.error(f"그래프 편집 오류: {e}")
            logger.exception("Graph editor error")


# ── Save / Export ─────────────────────────────────────────────────────────────

def render_save_section(db_path: str, analysis_json: dict):
    """Inline save controls — renders inside the Knowledge Graph page (no tab switch)."""
    with st.expander("💾 그래프 이미지 저장", expanded=False):
        st.caption(
            "PNG 파일에 그래프 데이터가 메타데이터로 포함됩니다. "
            "공유 후 재복원이 가능합니다."
        )
        include_emb = st.checkbox(
            "임베딩 포함 (파일 크기 큼, 벡터 검색 품질 보존)",
            value=False,
            key="save_with_embeddings",
        )
        if st.button("🖼️ 이미지 생성", key="gen_save_image"):
            with st.spinner("이미지 생성 중..."):
                buf = generate_static_graph_image(db_path, analysis_json, include_embeddings=include_emb)
            if buf:
                st.session_state["_save_image_buf"] = buf.getvalue()
                st.success("이미지가 생성되었습니다. 아래 버튼으로 다운로드하세요.")

        if st.session_state.get("_save_image_buf"):
            st.download_button(
                "📥 PNG 다운로드",
                data=st.session_state["_save_image_buf"],
                file_name="speaknode_graph.png",
                mime="image/png",
                key="download_graph_png",
            )


def generate_static_graph_image(db_path: str, analysis_json: dict, include_embeddings: bool = False):
    """Render the DB graph to a PNG with embedded payload metadata."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import networkx as nx

    _set_korean_font()
    try:
        with KuzuManager(db_path=db_path, config=_config) as manager:
            G = nx.DiGraph()
            labels: dict = {}

            for (name,) in manager.execute_cypher("MATCH (p:Person) RETURN p.name"):
                G.add_node(name, color=_NODE_COLORS["person"])
                labels[name] = name
            for (title,) in manager.execute_cypher("MATCH (t:Topic) RETURN t.title"):
                G.add_node(title, color=_NODE_COLORS["topic"])
                labels[title] = title
            for (desc,) in manager.execute_cypher("MATCH (d:Decision) RETURN d.description"):
                lbl = (desc[:14] + "…") if len(desc) > 14 else desc
                G.add_node(desc, color=_NODE_COLORS["decision"])
                labels[desc] = lbl
            for (desc,) in manager.execute_cypher("MATCH (t:Task) RETURN t.description"):
                lbl = (desc[:14] + "…") if len(desc) > 14 else desc
                G.add_node(desc, color=_NODE_COLORS["task"])
                labels[desc] = lbl

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

            try:
                for name, etype, _ in manager.execute_cypher(
                    "MATCH (e:Entity) RETURN e.name, e.entity_type, e.description"
                ):
                    lbl = (name[:14] + "…") if len(name) > 14 else name
                    G.add_node(name, color=_NODE_COLORS["entity"])
                    labels[name] = lbl
                for src, _, tgt in manager.execute_cypher(
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
                pass

            graph_dump = manager.export_graph_dump(include_embeddings=include_embeddings)

        fig, ax = plt.subplots(figsize=(12, 7), facecolor="#0f172a")
        ax.set_facecolor("#0f172a")
        pos = nx.spring_layout(G, k=1.0, seed=42)
        node_colors = [nx.get_node_attributes(G, "color").get(n, "#bdc3c7") for n in G.nodes()]
        nx.draw(
            G, pos, ax=ax,
            with_labels=True, labels=labels,
            node_color=node_colors, node_size=1600,
            font_size=9, font_weight="bold",
            edge_color="#475569", alpha=0.92,
            font_family=plt.rcParams["font.family"][0],
        )

        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", facecolor="#0f172a")
        plt.close(fig)
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
        logger.exception("Static graph image generation failed")
        return None


# ── Import Card UI ────────────────────────────────────────────────────────────

def render_import_card_ui(share_manager):
    st.divider()
    st.subheader("📂 지식 그래프 이미지 가져오기")
    import_file = st.file_uploader(
        "SpeakNode 그래프 이미지 업로드 (PNG)", type=["png"], key="import_card"
    )
    if import_file:
        # Use mkstemp to guarantee an absolute, unique temp path
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".png", prefix="speaknode_import_")
        try:
            with os.fdopen(tmp_fd, "wb") as f:
                f.write(import_file.getbuffer())
            data = share_manager.load_data_from_image(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        if data:
            st.success("이미지에서 데이터를 추출했습니다.")
            return data
        else:
            st.error("이 이미지에서 SpeakNode 데이터를 찾을 수 없습니다.")
            return None
    return None
