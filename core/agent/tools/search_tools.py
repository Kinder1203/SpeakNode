# vector, graph, and hybrid search.

from __future__ import annotations
from core.agent.tools import default_registry as registry


def _to_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@registry.register(
    "search_by_meaning",
    "의미 기반으로 관련 발언을 검색합니다. 인자: query(str). 특정 키워드나 주제에 대한 발언을 찾을 때 사용."
)
def search_by_meaning(args: dict, db, rag) -> str:
    query = (args.get("query") or args.get("keyword") or "").strip()
    top_k = _to_int(args.get("top_k", 5), 5)
    results = rag.vector_search(query, db, top_k=top_k)
    if not results:
        return "관련 발언을 찾지 못했습니다."
    lines = []
    for r in results:
        speaker = r.get('speaker') or '알 수 없음'
        meeting = r.get('meeting_title') or ''
        meeting_tag = f" [{meeting}]" if meeting else ""
        lines.append(f"[{r.get('start', 0):.1f}s] {speaker}: {r['text']}{meeting_tag} (유사도: {r.get('score', 0):.3f})")
    return "\n".join(lines)


@registry.register(
    "search_by_structure",
    '구조적 관계를 탐색합니다. 인자: entity_type("topic"|"task"|"decision"|"person"|"meeting"|"entity"), keyword(str, 선택).'
)
def search_by_structure(args: dict, db, rag) -> str:
    entity_type = (args.get("entity_type") or "").strip().lower()
    keyword = (args.get("keyword") or args.get("query") or "").strip()
    limit = _to_int(args.get("limit", 10), 10)
    person_name = (args.get("person_name") or "").strip()
    topic_title = (args.get("topic_title") or "").strip()

    if not entity_type:
        q = keyword.lower()
        if any(token in q for token in ["할 일", "task", "todo", "담당"]):
            entity_type = "task"
        elif any(token in q for token in ["결정", "합의", "decision"]):
            entity_type = "decision"
        elif any(token in q for token in ["참여", "누가", "사람", "담당자", "person"]):
            entity_type = "person"
        elif any(token in q for token in ["회의", "meeting", "요약"]):
            entity_type = "meeting"
        elif any(token in q for token in ["기술", "개념", "조직", "이벤트", "entity", "관계"]):
            entity_type = "entity"
        else:
            entity_type = "topic"

    if entity_type == "topic":
        items = rag.graph_search_topics(db, keyword=keyword, limit=limit)
        if not items:
            return "등록된 주제가 없습니다."
        lines = []
        for t in items:
            raw_title = t.get("id", t["title"])
            try:
                prop_rows = db.execute_cypher(
                    "MATCH (p:Person)-[:PROPOSED]->(tp:Topic {title: $title}) "
                    "RETURN p.name LIMIT 3",
                    {"title": raw_title},
                )
                proposers = [r[0] for r in prop_rows]
            except Exception:
                proposers = []
            try:
                dec_rows = db.execute_cypher(
                    "MATCH (tp:Topic {title: $title})-[:RESULTED_IN]->(d:Decision) "
                    "RETURN d.description LIMIT 5",
                    {"title": raw_title},
                )
                decisions = [r[0] for r in dec_rows]
            except Exception:
                decisions = []
            proposer_str = ", ".join(proposers) if proposers else "미지정"
            line = f"### {t['title']}\n  요약: {t.get('summary', '')}\n  제안자: {proposer_str}"
            if decisions:
                line += "\n  결정 사항:"
                for d in decisions:
                    line += f"\n    - {d}"
            lines.append(line)
        return "\n".join(lines)

    elif entity_type == "task":
        items = rag.graph_search_tasks(
            db,
            person_name=person_name,
            keyword=keyword if not person_name else "",
            limit=limit,
        )
        if not items:
            return "등록된 할 일이 없습니다."
        lines = []
        for t in items:
            deadline = t.get("deadline") or "미정"
            assignee = t.get("assignee", "미지정")
            lines.append(
                f"- {t['description']} (담당: {assignee}, 기한: {deadline}, 상태: {t.get('status', '?')})"
            )
        return "\n".join(lines)

    elif entity_type == "decision":
        items = rag.graph_search_decisions(
            db,
            topic_title=topic_title,
            keyword=keyword,
            limit=limit,
        )
        if not items:
            return "등록된 결정 사항이 없습니다."
        lines = []
        for d in items:
            desc = d.get("description", "")
            try:
                topic_rows = db.execute_cypher(
                    "MATCH (t:Topic)-[:RESULTED_IN]->(dd:Decision {description: $ddesc}) "
                    "RETURN t.title LIMIT 1",
                    {"ddesc": desc},
                )
                source_topic = topic_rows[0][0] if topic_rows else None
            except Exception:
                source_topic = None
            line = f"- {desc}"
            if source_topic:
                line += f" (관련 주제: {source_topic})"
            lines.append(line)
        return "\n".join(lines)

    elif entity_type == "person":
        items = rag.graph_search_people(db, keyword=keyword, limit=limit)
        if not items:
            return "등록된 참여자가 없습니다."

        lines = []
        for p in items:
            name = p['name']
            lines.append(f"### {name} ({p.get('role', 'Member')})")

            # Suggested Topics
            try:
                topic_rows = db.execute_cypher(
                    "MATCH (p:Person {name: $name})-[:PROPOSED]->(t:Topic) "
                    "RETURN t.title, t.summary LIMIT $lim",
                    {"name": name, "lim": limit},
                )
                if topic_rows:
                    lines.append("  제안 주제:")
                    for r in topic_rows:
                        lines.append(f"    - {r[0]}: {r[1] or ''}")
            except Exception:
                pass

            # assigned task
            try:
                tasks = rag.graph_search_tasks(db, person_name=name, limit=limit)
                if tasks:
                    lines.append("  할당된 할 일:")
                    for t in tasks:
                        lines.append(f"    - {t['description']} (상태: {t.get('status', '?')})")
            except Exception:
                pass

            # Speeches (last 5)
            try:
                utt_rows = db.execute_cypher(
                    "MATCH (p:Person {name: $name})-[:SPOKE]->(u:Utterance) "
                    "RETURN u.text, u.startTime ORDER BY u.startTime LIMIT $lim",
                    {"name": name, "lim": min(5, limit)},
                )
                if utt_rows:
                    lines.append("  주요 발언:")
                    for r in utt_rows:
                        time_str = f"[{r[1]:.1f}s] " if r[1] else ""
                        lines.append(f"    - {time_str}{r[0]}")
            except Exception:
                pass

            # Related Entities
            try:
                ent_rows = db.execute_cypher(
                    "MATCH (p:Person {name: $name})-[:SPOKE]->(:Utterance)<-[:CONTAINS]-(m:Meeting)-[:HAS_ENTITY]->(e:Entity) "
                    "RETURN DISTINCT e.name, e.entity_type LIMIT $lim",
                    {"name": name, "lim": limit},
                )
                if ent_rows:
                    lines.append("  관련 엔티티:")
                    for r in ent_rows:
                        etype = f"[{r[1]}] " if r[1] else ""
                        lines.append(f"    - {etype}{r[0]}")
            except Exception:
                pass

        return "\n".join(lines)

    elif entity_type == "meeting":
        items = rag.graph_search_meetings(db, keyword=keyword, limit=limit)
        if not items:
            return "등록된 회의가 없습니다."
        lines = []
        for i, m in enumerate(items):
            if i < 5:
                summary = db.get_meeting_summary(m['id'])
                if summary:
                    lines.append(f"### {summary.get('title', m['title'])} ({summary.get('date', '')})")
                    s_topics = summary.get("topics", [])
                    if s_topics:
                        lines.append("  주제:")
                        for st in s_topics:
                            lines.append(f"    - {st['title']}: {st.get('summary', '')}")
                    s_decs = summary.get("decisions", [])
                    if s_decs:
                        lines.append("  결정 사항:")
                        for sd in s_decs:
                            lines.append(f"    - {sd['description']}")
                    s_tasks = summary.get("tasks", [])
                    if s_tasks:
                        lines.append("  할 일:")
                        for stk in s_tasks:
                            lines.append(f"    - {stk['description']} (담당: {stk.get('assignee', '미지정')}, 상태: {stk.get('status', '?')})")
                    s_ppl = summary.get("people", [])
                    if s_ppl:
                        names = ", ".join(sp['name'] for sp in s_ppl)
                        lines.append(f"  참여자: {names}")
                else:
                    lines.append(f"- [{m['id']}] {m['title']} ({m.get('date', '')})")
            else:
                lines.append(f"- [{m['id']}] {m['title']} ({m.get('date', '')})")
        return "\n".join(lines)

    elif entity_type == "entity":
        etype_filter = (args.get("entity_type_filter") or "").strip()
        items = rag.graph_search_entities(db, keyword=keyword, entity_type=etype_filter, limit=limit)
        if not items:
            return "등록된 엔티티가 없습니다."
        lines = []
        for e in items:
            et = e.get("entity_type", "")
            desc = e.get("description", "")
            label = f"[{et}] " if et else ""
            lines.append(f"- {label}{e['name']}: {desc}")
        # Also include relations if available
        relations = rag.graph_search_entity_relations(db, entity_name=keyword, limit=limit)
        if relations:
            lines.append("\n관계:")
            for r in relations:
                lines.append(f"  - {r['source']} —[{r['relation_type']}]→ {r['target']}")
        return "\n".join(lines)

    else:
        return f"알 수 없는 entity_type: {entity_type}"


@registry.register(
    "hybrid_search",
    "의미 + 구조 결합 검색. 인자: query(str), search_hints(list[str], 선택). 복합적인 질문에 사용."
)
def hybrid_search(args: dict, db, rag) -> str:
    query = (args.get("query") or args.get("keyword") or "").strip()
    top_k = _to_int(args.get("top_k", 5), 5)
    graph_k = _to_int(args.get("graph_k", 8), 8)
    search_hints = args.get("search_hints") or []
    if not isinstance(search_hints, list):
        search_hints = []
    result = rag.hybrid_search(query, db, top_k=top_k, graph_k=graph_k, search_hints=search_hints)
    return result.get("merged_context", "(결과 없음)")
