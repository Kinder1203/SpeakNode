"""
검색 도구 모음: Vector / Graph / Hybrid Search
"""

from __future__ import annotations

import json
from core.tools import default_registry as registry


@registry.register(
    "search_by_meaning",
    "의미 기반으로 관련 발언을 검색합니다. 인자: query(str). 특정 키워드나 주제에 대한 발언을 찾을 때 사용."
)
def search_by_meaning(args: dict, db, rag) -> str:
    query = args.get("query", "")
    results = rag.vector_search(query, db, top_k=5)
    if not results:
        return "관련 발언을 찾지 못했습니다."
    lines = []
    for r in results:
        lines.append(f"[{r.get('start', 0):.1f}s] {r['text']} (유사도: {r.get('score', 0):.3f})")
    return "\n".join(lines)


@registry.register(
    "search_by_structure",
    '구조적 관계를 탐색합니다. 인자: entity_type("topic"|"task"|"decision"|"person"|"meeting"), keyword(str, 선택).'
)
def search_by_structure(args: dict, db, rag) -> str:
    entity_type = args.get("entity_type", "topic")
    keyword = args.get("keyword", "")

    if entity_type == "topic":
        items = rag.graph_search_topics(db, keyword=keyword)
        if not items:
            return "등록된 주제가 없습니다."
        return "\n".join(f"- {t['title']}: {t.get('summary', '')}" for t in items)

    elif entity_type == "task":
        items = rag.graph_search_tasks(db, person_name=keyword)
        if not items:
            return "등록된 할 일이 없습니다."
        return "\n".join(
            f"- {t['description']} (담당: {t.get('assignee', '미지정')}, 상태: {t.get('status', '?')})"
            for t in items
        )

    elif entity_type == "decision":
        items = rag.graph_search_decisions(db, topic_title=keyword)
        if not items:
            return "등록된 결정 사항이 없습니다."
        return "\n".join(f"- {d['description']}" for d in items)

    elif entity_type == "person":
        items = rag.graph_search_people(db)
        if not items:
            return "등록된 참여자가 없습니다."
        return "\n".join(f"- {p['name']} ({p.get('role', 'Member')})" for p in items)

    elif entity_type == "meeting":
        items = rag.graph_search_meetings(db)
        if not items:
            return "등록된 회의가 없습니다."
        return "\n".join(f"- [{m['id']}] {m['title']} ({m.get('date', '')})" for m in items)

    else:
        return f"알 수 없는 entity_type: {entity_type}"


@registry.register(
    "hybrid_search",
    "의미 + 구조 결합 검색. 인자: query(str). 복합적인 질문에 사용."
)
def hybrid_search(args: dict, db, rag) -> str:
    query = args.get("query", "")
    result = rag.hybrid_search(query, db, top_k=5)
    return result.get("merged_context", "(결과 없음)")
