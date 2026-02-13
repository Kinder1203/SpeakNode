"""
SpeakNode Hybrid RAG (검색 엔진)
=================================
Vector RAG (의미 기반) + Graph RAG (구조 기반) 결합 검색.
Agent의 Tool이 이 모듈을 호출하여 회의 DB에서 정보를 탐색합니다.
"""

import json
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from core.config import SpeakNodeConfig
from core.db.kuzu_manager import KuzuManager

FORBIDDEN_CYPHER_TOKENS = (
    "CREATE",
    "MERGE",
    "SET",
    "DELETE",
    "DROP",
    "ALTER",
    "INSERT",
    "REMOVE",
)


class HybridRAG:
    """
    Hybrid RAG Engine
    - Vector Search: 임베딩 코사인 유사도로 관련 발언 검색
    - Graph Search: PROPOSED, ASSIGNED_TO, RESULTED_IN 등 구조적 관계 탐색
    - Fusion: 두 결과를 합산하여 중복 제거 후 LLM 컨텍스트 생성
    """

    def __init__(self, config: SpeakNodeConfig = None):
        self.config = config or SpeakNodeConfig()
        self._embedder = None  # Lazy Loading
        self._cypher_llm = None

    @property
    def embedder(self):
        """SentenceTransformer — 최초 검색 시 1회만 로드"""
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer
            print("   ⏳ Loading Embedding Model (HybridRAG)...")
            self._embedder = SentenceTransformer(self.config.embedding_model)
        return self._embedder

    @property
    def cypher_llm(self):
        """자연어 -> Cypher 변환용 LLM (JSON 출력 강제)"""
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
            return False, "생성된 Cypher 쿼리가 비어 있습니다."

        normalized_start = re.sub(r"\s+", " ", query.strip()).upper()
        if not normalized_start.startswith(("MATCH ", "OPTIONAL MATCH ", "WITH ")):
            return False, "허용되지 않은 Cypher 시작 절입니다. (MATCH/OPTIONAL MATCH/WITH만 허용)"

        upper_query = query.upper()
        if "RETURN" not in upper_query:
            return False, "Cypher 쿼리에 RETURN 절이 없습니다."

        for token in FORBIDDEN_CYPHER_TOKENS:
            if re.search(rf"\b{token}\b", upper_query):
                return False, f"읽기 전용 정책 위반 토큰 감지: {token}"
        return True, ""

    def cypher_search(self, question: str, db: KuzuManager, limit: int = 20) -> dict:
        """자연어 질문을 읽기 전용 Cypher로 변환해 실행합니다."""
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

    # ================================================================
    # 🔍 Vector RAG — 의미 기반 검색
    # ================================================================

    def vector_search(self, query: str, db: KuzuManager, top_k: int = 5) -> list[dict]:
        """자연어 질의를 벡터화하여 가장 유사한 Utterance를 찾습니다."""
        query_vec = self.embedder.encode(query).tolist()
        results = db.search_similar_utterances(query_vec, top_k=top_k)
        return results

    # ================================================================
    # 🕸️ Graph RAG — 구조 기반 검색
    # ================================================================

    def graph_search_topics(self, db: KuzuManager, keyword: str = "", limit: int = 10) -> list[dict]:
        """Topic 노드 검색. keyword가 있으면 CONTAINS 필터."""
        return db.get_all_topics(limit=limit, keyword=keyword)

    def graph_search_tasks(
        self, db: KuzuManager, person_name: str = "", keyword: str = "", limit: int = 10
    ) -> list[dict]:
        """Task 노드 검색. person_name이 있으면 해당 인물의 Task만."""
        if person_name:
            return db.get_person_tasks(person_name, limit=limit)
        return db.get_all_tasks(limit=limit, keyword=keyword)

    def graph_search_decisions(
        self, db: KuzuManager, topic_title: str = "", keyword: str = "", limit: int = 10
    ) -> list[dict]:
        """Decision 노드 검색. topic_title이 있으면 해당 Topic의 Decision만."""
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
        """모든 Person 노드 조회."""
        return db.get_all_people(limit=limit, keyword=keyword)

    def graph_search_meetings(self, db: KuzuManager, keyword: str = "", limit: int = 20) -> list[dict]:
        """모든 Meeting 노드 조회."""
        return db.get_all_meetings(limit=limit, keyword=keyword)

    # ================================================================
    # 🔄 Hybrid Search — 결합 검색
    # ================================================================

    def hybrid_search(self, query: str, db: KuzuManager, top_k: int = 5, graph_k: int = 8) -> dict:
        """
        Vector Search + Graph Search 결합.
        질의에서 키워드를 추출하여 양쪽 모두 검색한 뒤 통합 컨텍스트를 생성합니다.
        """
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
