"""
SpeakNode Hybrid RAG (검색 엔진)
=================================
Vector RAG (의미 기반) + Graph RAG (구조 기반) 결합 검색.
Agent의 Tool이 이 모듈을 호출하여 회의 DB에서 정보를 탐색합니다.
"""

from core.config import SpeakNodeConfig
from core.db.kuzu_manager import KuzuManager


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

    @property
    def embedder(self):
        """SentenceTransformer — 최초 검색 시 1회만 로드"""
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer
            print("   ⏳ Loading Embedding Model (HybridRAG)...")
            self._embedder = SentenceTransformer(self.config.embedding_model)
        return self._embedder

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

    def graph_search_topics(self, db: KuzuManager, keyword: str = "") -> list[dict]:
        """Topic 노드 검색. keyword가 있으면 CONTAINS 필터."""
        if keyword:
            rows = db.execute_cypher(
                "MATCH (t:Topic) WHERE t.title CONTAINS $kw OR t.summary CONTAINS $kw "
                "RETURN t.title, t.summary",
                {"kw": keyword}
            )
        else:
            rows = db.execute_cypher("MATCH (t:Topic) RETURN t.title, t.summary")
        return [{"title": r[0], "summary": r[1]} for r in rows]

    def graph_search_tasks(self, db: KuzuManager, person_name: str = "") -> list[dict]:
        """Task 노드 검색. person_name이 있으면 해당 인물의 Task만."""
        if person_name:
            return db.get_person_tasks(person_name)
        return db.get_all_tasks()

    def graph_search_decisions(self, db: KuzuManager, topic_title: str = "") -> list[dict]:
        """Decision 노드 검색. topic_title이 있으면 해당 Topic의 Decision만."""
        if topic_title:
            return db.get_topic_decisions(topic_title)
        rows = db.execute_cypher("MATCH (d:Decision) RETURN d.description")
        return [{"description": r[0]} for r in rows]

    def graph_search_people(self, db: KuzuManager) -> list[dict]:
        """모든 Person 노드 조회."""
        rows = db.execute_cypher("MATCH (p:Person) RETURN p.name, p.role")
        return [{"name": r[0], "role": r[1]} for r in rows]

    def graph_search_meetings(self, db: KuzuManager) -> list[dict]:
        """모든 Meeting 노드 조회."""
        rows = db.execute_cypher(
            "MATCH (m:Meeting) RETURN m.id, m.title, m.date, m.source_file"
        )
        return [{"id": r[0], "title": r[1], "date": r[2], "source_file": r[3]} for r in rows]

    # ================================================================
    # 🔄 Hybrid Search — 결합 검색
    # ================================================================

    def hybrid_search(self, query: str, db: KuzuManager, top_k: int = 5) -> dict:
        """
        Vector Search + Graph Search 결합.
        질의에서 키워드를 추출하여 양쪽 모두 검색한 뒤 통합 컨텍스트를 생성합니다.
        """
        # 1. Vector Search: 의미적으로 유사한 발언 검색
        vector_results = self.vector_search(query, db, top_k=top_k)

        # 2. Graph Search: 구조적 관련 정보 수집
        topics = self.graph_search_topics(db, keyword=query[:20] if len(query) > 5 else "")
        tasks = self.graph_search_tasks(db)
        decisions = self.graph_search_decisions(db)
        people = self.graph_search_people(db)

        graph_results = {
            "topics": topics,
            "tasks": tasks,
            "decisions": decisions,
            "people": people,
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

        merged_context = "\n".join(context_parts) if context_parts else "(검색 결과 없음)"

        return {
            "vector_results": vector_results,
            "graph_results": graph_results,
            "merged_context": merged_context,
        }
