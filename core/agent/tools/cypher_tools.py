"""
Cypher 도구: 자연어를 읽기 전용 Cypher로 변환해 구조 질의 실행
"""

from __future__ import annotations

from core.agent.tools import default_registry as registry


def _to_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@registry.register(
    "search_by_cypher",
    "자연어 질문을 읽기 전용 Cypher로 변환해 실행합니다. 인자: query(str), limit(int, 선택).",
)
def search_by_cypher(args: dict, db, rag) -> str:
    query = (args.get("query") or args.get("question") or "").strip()
    limit = _to_int(args.get("limit", 20), 20)
    if not query:
        return "질문이 비어 있어 Cypher 검색을 수행할 수 없습니다."

    result = rag.cypher_search(query, db, limit=limit)
    if not result.get("ok"):
        return f"Cypher 검색 실패: {result.get('error', 'unknown error')}"

    rows = result.get("rows", [])
    rendered_rows = "\n".join(f"- {row}" for row in rows[:limit]) if rows else "(결과 없음)"
    return f"""[Generated Cypher]
{result.get("query", "")}

[Results]
{rendered_rows}"""
