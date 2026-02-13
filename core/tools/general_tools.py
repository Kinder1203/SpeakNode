"""
일반 도구: DB 검색 불필요한 직접 답변
"""

from __future__ import annotations

from core.tools import default_registry as registry


@registry.register(
    "direct_answer",
    "DB 검색이 필요 없는 일반적인 질문에 직접 답변합니다. 인자: 없음."
)
def direct_answer(args: dict, db, rag) -> str:
    return ""  # 직접 답변 — Synthesizer가 LLM으로 응답 생성
