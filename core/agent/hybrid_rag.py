"""Hybrid RAG engine combining vector and graph search."""

import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from core.config import SpeakNodeConfig
from core.db.kuzu_manager import KuzuManager
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
        prompt = """You are a Cypher query generator for a meeting graph.
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

Use meeting-aware relations (HAS_TASK, HAS_DECISION, DISCUSSED, CONTAINS) when possible.
Topic.title / Task.description / Decision.description can be stored as "<meeting_id>::<plain_text>".
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
                "error": f"Cypher 생성 실패: {exc}",
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
                "error": f"Cypher 실행 실패: {exc}",
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

    def hybrid_search(self, query: str, db: KuzuManager, top_k: int = 5, graph_k: int = 8) -> dict:
        """Fuse vector and graph search results into a single context."""
        query = (query or "").strip()
        q = query.lower()

        ask_tasks = any(token in q for token in ["할 일", "task", "todo", "담당", "액션"])
        ask_decisions = any(token in q for token in ["결정", "합의", "decision"])
        ask_people = any(token in q for token in ["참여", "누가", "사람", "담당자", "person"])
        ask_meetings = any(token in q for token in ["회의", "meeting", "요약", "언제"])

        # 1. Vector Search: 의미적으로 유사한 발언 검색
        vector_results = self.vector_search(query, db, top_k=top_k)

        # 2. Graph Search: 구조적 관련 정보 수집
        topics = self.graph_search_topics(db, keyword=query, limit=graph_k)
        tasks = self.graph_search_tasks(db, keyword=query if ask_tasks else "", limit=graph_k) if ask_tasks else []
        decisions = (
            self.graph_search_decisions(db, keyword=query if ask_decisions else "", limit=graph_k)
            if ask_decisions else []
        )
        people = self.graph_search_people(db, keyword=query if ask_people else "", limit=graph_k) if ask_people else []
        meetings = self.graph_search_meetings(db, keyword=query if ask_meetings else "", limit=graph_k) if ask_meetings else []

        if not ask_tasks and not ask_decisions and not ask_people and not ask_meetings:
            # 일반 질문은 요약 컨텍스트 최소치만 유지
            tasks = self.graph_search_tasks(db, limit=min(3, graph_k))
            decisions = self.graph_search_decisions(db, limit=min(3, graph_k))

        graph_results = {
            "topics": topics,
            "tasks": tasks,
            "decisions": decisions,
            "people": people,
            "meetings": meetings,
        }

        # 3. 통합 컨텍스트 생성 (LLM 프롬프트에 주입할 문자열)
        context_parts = []

        if vector_results:
            context_parts.append("## 관련 발언 (의미 기반 검색)")
            for vr in vector_results:
                context_parts.append(
                    f"- [{vr.get('start', 0):.1f}s] {vr['text']} (유사도: {vr.get('score', 0):.3f})"
                )

        if topics:
            context_parts.append("\n## 주제 (Topic)")
            for t in topics:
                context_parts.append(f"- **{t['title']}**: {t.get('summary', '')}")

        if tasks:
            context_parts.append("\n## 할 일 (Task)")
            for t in tasks:
                assignee = t.get("assignee", "미지정")
                context_parts.append(f"- {t['description']} (담당: {assignee}, 상태: {t.get('status', '?')})")

        if decisions:
            context_parts.append("\n## 결정 사항 (Decision)")
            for d in decisions:
                context_parts.append(f"- {d['description']}")

        if people:
            context_parts.append("\n## 참여자")
            for p in people:
                context_parts.append(f"- {p['name']} ({p.get('role', 'Member')})")

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
