"""Hybrid RAG engine combining vector and graph search."""

import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from core.config import SpeakNodeConfig
from core.db.kuzu_manager import KuzuManager, decode_scoped_value
from core.embedding import get_embedder

logger = logging.getLogger(__name__)

FORBIDDEN_CYPHER_TOKENS = (
    "CREATE",
    "MERGE",
    "SET",
    "DELETE",
    "DROP",
    "ALTER",
    "INSERT",
    "REMOVE",
    "CALL",
    "COPY",
    "LOAD",
    "UNWIND",
    "PROFILE",
    "EXPLAIN",
)


class HybridRAG:
    """Vector + Graph fusion search engine."""

    def __init__(self, config: SpeakNodeConfig = None):
        self.config = config or SpeakNodeConfig()
        self._cypher_llm = None

    @property
    def embedder(self):
        return get_embedder(self.config.embedding_model)

    @property
    def cypher_llm(self):
        if self._cypher_llm is None:
            self._cypher_llm = ChatOllama(
                model=self.config.agent_model,
                temperature=0.0,
                format="json",
            )
        return self._cypher_llm

    def _generate_cypher(self, question: str, limit: int) -> tuple[str, dict]:
        prompt = """You are a Cypher query generator for a meeting/knowledge graph.
Return JSON only:
{"query": "<cypher>", "params": { ... }}

Hard rules:
1) Generate read-only query only (MATCH/OPTIONAL MATCH/WITH/RETURN/ORDER BY/LIMIT).
2) Never use CREATE/MERGE/SET/DELETE/DROP/ALTER/INSERT/REMOVE.
3) Always include RETURN.
4) Keep query concise and bounded by LIMIT.

Schema:
- Person(name, role)
- Topic(title, summary)
- Task(description, deadline, status)
- Decision(description)
- Utterance(id, text, startTime, endTime, embedding)
- Meeting(id, title, date, source_file)
- Entity(name, entity_type, description)

Relations:
- (Person)-[:PROPOSED]->(Topic)
- (Person)-[:ASSIGNED_TO]->(Task)
- (Topic)-[:RESULTED_IN]->(Decision)
- (Person)-[:SPOKE]->(Utterance)
- (Utterance)-[:NEXT]->(Utterance)
- (Meeting)-[:DISCUSSED]->(Topic)
- (Meeting)-[:CONTAINS]->(Utterance)
- (Meeting)-[:HAS_TASK]->(Task)
- (Meeting)-[:HAS_DECISION]->(Decision)
- (Entity)-[:RELATED_TO {relation_type}]->(Entity)
- (Topic)-[:MENTIONS]->(Entity)
- (Meeting)-[:HAS_ENTITY]->(Entity)

Entity.entity_type can be: person, technology, organization, concept, event.
Use meeting-aware relations (HAS_TASK, HAS_DECISION, DISCUSSED, CONTAINS, HAS_ENTITY) when possible.
Topic.title / Task.description / Decision.description / Entity.name can be stored as "<meeting_id>::<plain_text>".
For user-facing keyword filtering, prefer CONTAINS over exact equality.
"""
        response = self.cypher_llm.invoke(
            [
                SystemMessage(content=prompt),
                HumanMessage(content=f"Question: {question}\nDefault limit: {limit}"),
            ]
        )
        parsed = json.loads(response.content.strip())
        query = str(parsed.get("query", "")).strip()
        params = parsed.get("params", {})
        if not isinstance(params, dict):
            params = {}
        return query, params

    def _validate_read_only_cypher(self, query: str) -> tuple[bool, str]:
        if not query:
            return False, "Empty Cypher query."

        normalized_start = re.sub(r"\s+", " ", query.strip()).upper()
        if not normalized_start.startswith(("MATCH ", "OPTIONAL MATCH ", "WITH ")):
            return False, "Cypher must start with MATCH/OPTIONAL MATCH/WITH."

        upper_query = query.upper()
        if ";" in query:
            return False, "Multiple statements are not allowed."
        if "RETURN" not in upper_query:
            return False, "Cypher query must contain a RETURN clause."

        for token in FORBIDDEN_CYPHER_TOKENS:
            if re.search(rf"\b{token}\b", upper_query):
                return False, f"Read-only policy violation: {token}"
        return True, ""

    def cypher_search(self, question: str, db: KuzuManager, limit: int = 20) -> dict:
        """Translate a natural language question to read-only Cypher and execute it."""
        safe_limit = max(1, min(int(limit or 20), 200))
        try:
            query, params = self._generate_cypher(question, safe_limit)
        except Exception as exc:
            return {
                "ok": False,
                "error": f"Cypher execution failed: {exc}",
                "query": "",
                "rows": [],
            }

        query = query.rstrip(";").strip()
        if "LIMIT" not in query.upper():
            query = f"{query} LIMIT {safe_limit}"

        is_valid, message = self._validate_read_only_cypher(query)
        if not is_valid:
            return {
                "ok": False,
                "error": message,
                "query": query,
                "rows": [],
            }

        try:
            rows = db.execute_cypher(query, params)
            serializable_rows = [list(row) for row in rows]
            return {"ok": True, "error": "", "query": query, "rows": serializable_rows}
        except Exception as exc:
            return {
                "ok": False,
                "error": f"Cypher execution failed: {exc}",
                "query": query,
                "rows": [],
            }

    def vector_search(self, query: str, db: KuzuManager, top_k: int = 5) -> list[dict]:
        """Find the most similar utterances by embedding cosine similarity."""
        query_vec = self.embedder.encode(query).tolist()
        return db.search_similar_utterances(query_vec, top_k=top_k)

    def graph_search_topics(self, db: KuzuManager, keyword: str = "", limit: int = 10) -> list[dict]:
        return db.get_all_topics(limit=limit, keyword=keyword)

    def graph_search_tasks(
        self, db: KuzuManager, person_name: str = "", keyword: str = "", limit: int = 10
    ) -> list[dict]:
        if person_name:
            return db.get_person_tasks(person_name, limit=limit)
        return db.get_all_tasks(limit=limit, keyword=keyword)

    def graph_search_decisions(
        self, db: KuzuManager, topic_title: str = "", keyword: str = "", limit: int = 10
    ) -> list[dict]:
        if topic_title:
            return db.get_topic_decisions(topic_title, limit=limit)
        if keyword:
            rows = db.execute_cypher(
                "MATCH (d:Decision) OPTIONAL MATCH (t:Topic)-[:RESULTED_IN]->(d) "
                "WHERE d.description CONTAINS $kw OR t.title CONTAINS $kw "
                "RETURN d.description LIMIT $lim",
                {"kw": keyword, "lim": limit},
            )
        else:
            rows = db.execute_cypher(
                "MATCH (d:Decision) RETURN d.description LIMIT $lim",
                {"lim": limit},
            )
        return [{"description": r[0]} for r in rows]

    def graph_search_people(self, db: KuzuManager, keyword: str = "", limit: int = 10) -> list[dict]:
        return db.get_all_people(limit=limit, keyword=keyword)

    def graph_search_meetings(self, db: KuzuManager, keyword: str = "", limit: int = 20) -> list[dict]:
        return db.get_all_meetings(limit=limit, keyword=keyword)

    def graph_search_entities(
        self, db: KuzuManager, keyword: str = "", entity_type: str = "", limit: int = 10
    ) -> list[dict]:
        """Search Entity nodes with optional keyword/type filter."""
        try:
            return db.get_all_entities(limit=limit, keyword=keyword, entity_type=entity_type)
        except Exception:
            # Graceful fallback for old DBs without Entity table
            return []

    def graph_search_entity_relations(
        self, db: KuzuManager, entity_name: str = "", limit: int = 10
    ) -> list[dict]:
        """Search RELATED_TO edges between entities."""
        try:
            return db.get_entity_relations(entity_name=entity_name, limit=limit)
        except Exception:
            return []

    def hybrid_search(self, query: str, db: KuzuManager, top_k: int = 5, graph_k: int = 8) -> dict:
        """Fuse vector and graph search results into a single context."""
        query = (query or "").strip()
        q = query.lower()

        ask_tasks = any(token in q for token in ["할 일", "task", "todo", "담당", "액션"])
        ask_decisions = any(token in q for token in ["결정", "합의", "decision"])
        ask_people = any(token in q for token in ["참여", "누가", "사람", "담당자", "person"])
        ask_meetings = any(token in q for token in ["회의", "meeting", "요약", "언제"])
        ask_entities = any(token in q for token in [
            "기술", "개념", "조직", "이벤트", "entity", "무엇", "뭐", "어떤",
            "관계", "연결", "관련", "역사", "발전",
        ])

        # Vector Search
        vector_results = self.vector_search(query, db, top_k=top_k)

        # Graph Search
        topics = self.graph_search_topics(db, keyword=query, limit=graph_k)
        tasks = self.graph_search_tasks(db, keyword=query if ask_tasks else "", limit=graph_k) if ask_tasks else []
        decisions = (
            self.graph_search_decisions(db, keyword=query if ask_decisions else "", limit=graph_k)
            if ask_decisions else []
        )
        people = self.graph_search_people(db, keyword=query if ask_people else "", limit=graph_k) if ask_people else []
        meetings = self.graph_search_meetings(db, keyword=query if ask_meetings else "", limit=graph_k) if ask_meetings else []

        # Entity search — always include a baseline, keyword-boost when relevant
        entities = self.graph_search_entities(db, keyword=query if ask_entities else "", limit=graph_k)
        entity_relations = self.graph_search_entity_relations(db, entity_name=query if ask_entities else "", limit=graph_k)

        if not ask_tasks and not ask_decisions and not ask_people and not ask_meetings:
            tasks = self.graph_search_tasks(db, limit=min(3, graph_k))
            decisions = self.graph_search_decisions(db, limit=min(3, graph_k))

        # If no specific intent detected and entities exist, always provide a baseline
        if not entities and not ask_entities:
            entities = self.graph_search_entities(db, limit=min(5, graph_k))

        graph_results = {
            "topics": topics,
            "tasks": tasks,
            "decisions": decisions,
            "people": people,
            "meetings": meetings,
            "entities": entities,
            "entity_relations": entity_relations,
        }

        # ── Enrich: topics → proposer + decisions ──
        for t in topics:
            raw_title = t.get("id", t["title"])
            try:
                prop_rows = db.execute_cypher(
                    "MATCH (p:Person)-[:PROPOSED]->(tp:Topic {title: $title}) "
                    "RETURN p.name LIMIT 3",
                    {"title": raw_title},
                )
                t["proposers"] = [r[0] for r in prop_rows]
            except Exception:
                t["proposers"] = []
            try:
                dec_rows = db.execute_cypher(
                    "MATCH (tp:Topic {title: $title})-[:RESULTED_IN]->(d:Decision) "
                    "RETURN d.description LIMIT 5",
                    {"title": raw_title},
                )
                t["decisions"] = [decode_scoped_value(r[0]) for r in dec_rows]
            except Exception:
                t["decisions"] = []

        # ── Enrich: people → proposed topics + assigned tasks ──
        for p in people:
            name = p.get("name", "")
            try:
                topic_rows = db.execute_cypher(
                    "MATCH (pe:Person {name: $name})-[:PROPOSED]->(t:Topic) "
                    "RETURN t.title LIMIT 5",
                    {"name": name},
                )
                p["proposed_topics"] = [decode_scoped_value(r[0]) for r in topic_rows]
            except Exception:
                p["proposed_topics"] = []
            try:
                task_rows = db.execute_cypher(
                    "MATCH (pe:Person {name: $name})-[:ASSIGNED_TO]->(t:Task) "
                    "RETURN t.description, t.status LIMIT 5",
                    {"name": name},
                )
                p["assigned_tasks"] = [
                    {"description": decode_scoped_value(r[0]), "status": r[1] or "?"}
                    for r in task_rows
                ]
            except Exception:
                p["assigned_tasks"] = []

        # Merge context
        context_parts = []

        if vector_results:
            context_parts.append("## 관련 발언 (의미 기반 검색)")
            for vr in vector_results:
                speaker = vr.get('speaker') or '알 수 없음'
                meeting = vr.get('meeting_title') or ''
                meeting_tag = f" [{meeting}]" if meeting else ""
                context_parts.append(
                    f"- [{vr.get('start', 0):.1f}s] **{speaker}**: {vr['text']}{meeting_tag} (유사도: {vr.get('score', 0):.3f})"
                )

        if topics:
            context_parts.append("\n## 주제 (Topic)")
            for t in topics:
                proposer_str = ", ".join(t.get("proposers", [])) or "미지정"
                line = f"- **{t['title']}**: {t.get('summary', '')} (제안: {proposer_str})"
                context_parts.append(line)
                for dec in t.get("decisions", []):
                    context_parts.append(f"  → 결정: {dec}")

        if entities:
            context_parts.append("\n## 핵심 엔티티 (Entity)")
            for e in entities:
                etype = e.get("entity_type", "")
                desc = e.get("description", "")
                label = f"[{etype}] " if etype else ""
                context_parts.append(f"- {label}**{e['name']}**: {desc}")

        if entity_relations:
            context_parts.append("\n## 엔티티 관계")
            for er in entity_relations:
                context_parts.append(
                    f"- {er['source']} —[{er['relation_type']}]→ {er['target']}"
                )

        if tasks:
            context_parts.append("\n## 할 일 (Task)")
            for t in tasks:
                assignee = t.get("assignee", "미지정")
                deadline = t.get("deadline") or "미정"
                context_parts.append(f"- {t['description']} (담당: {assignee}, 기한: {deadline}, 상태: {t.get('status', '?')})")

        if decisions:
            context_parts.append("\n## 결정 사항 (Decision)")
            for d in decisions:
                context_parts.append(f"- {decode_scoped_value(d['description'])}")

        if people:
            context_parts.append("\n## 참여자")
            for p in people:
                line = f"- **{p['name']}** ({p.get('role', 'Member')})"
                proposed = p.get("proposed_topics", [])
                assigned = p.get("assigned_tasks", [])
                if proposed:
                    line += f" | 제안: {', '.join(proposed)}"
                if assigned:
                    task_strs = [f"{a['description']}({a.get('status', '?')})" for a in assigned]
                    line += f" | 할 일: {', '.join(task_strs)}"
                context_parts.append(line)

        if meetings:
            context_parts.append("\n## 회의")
            for m in meetings:
                context_parts.append(f"- [{m['id']}] {m['title']} ({m.get('date', '')})")

        merged_context = "\n".join(context_parts) if context_parts else "(검색 결과 없음)"

        return {
            "vector_results": vector_results,
            "graph_results": graph_results,
            "merged_context": merged_context,
        }
