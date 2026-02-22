# direct answers that do not require DB lookup.

from __future__ import annotations

from core.agent.tools import default_registry as registry


@registry.register(
    "direct_answer",
    "DB 검색이 필요 없는 일반적인 질문에 직접 답변합니다. 인자: 없음."
)
def direct_answer(args: dict, db, rag) -> str:
    return ""  # Synthesizer generates response with LLM
