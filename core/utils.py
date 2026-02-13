"""
SpeakNode 공통 유틸리티
========================
여러 모듈에서 공유되는 비즈니스 로직을 단일 소스로 관리합니다.
중복 정의를 방지하고, 변경 시 한 곳만 수정하면 됩니다.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ================================================================
# Task 상태 정규화
# ================================================================

ALLOWED_TASK_STATUSES: frozenset[str] = frozenset(
    {"pending", "in_progress", "done", "blocked"}
)

TASK_STATUS_OPTIONS: list[str] = sorted(ALLOWED_TASK_STATUSES)

_TASK_STATUS_ALIASES: dict[str, str] = {
    "to do": "pending",
    "todo": "pending",
    "in progress": "in_progress",
    "complete": "done",
    "completed": "done",
}


def normalize_task_status(raw: str) -> str:
    """
    다양한 형식의 Task 상태 문자열을 허용된 상태값으로 정규화합니다.

    허용 상태: pending, in_progress, done, blocked
    허용되지 않는 값은 'pending'으로 기본 전환됩니다.
    """
    status = str(raw or "").strip().lower()
    normalized = _TASK_STATUS_ALIASES.get(status, status)
    return normalized if normalized in ALLOWED_TASK_STATUSES else "pending"


# ================================================================
# LLM Context Window 관리
# ================================================================

# 보수적 추정: 한국어 기준 1토큰 ≈ 1.5자, 영어 기준 1토큰 ≈ 4자.
# 혼합 텍스트를 감안하여 1토큰 ≈ 2자로 보수적 추정합니다.
_CHARS_PER_TOKEN_ESTIMATE = 2

# 기본 최대 컨텍스트 토큰 (Qwen2.5 14B 기준 32K 중 응답용 4K 예약)
DEFAULT_MAX_CONTEXT_TOKENS = 28_000


def estimate_token_count(text: str) -> int:
    """문자 수 기반으로 토큰 수를 보수적으로 추정합니다."""
    return len(text) // _CHARS_PER_TOKEN_ESTIMATE


def truncate_text(
    text: str,
    max_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
    *,
    keep: str = "head",
) -> str:
    """
    텍스트를 지정된 토큰 수 이내로 잘라냅니다.

    Args:
        text: 원본 텍스트
        max_tokens: 최대 허용 토큰 수
        keep: "head" (앞부분 보존) 또는 "tail" (뒷부분 보존)

    Returns:
        잘린 텍스트. 잘린 경우 말줄임 표시 포함.
    """
    if not text:
        return text
    max_chars = max_tokens * _CHARS_PER_TOKEN_ESTIMATE
    if len(text) <= max_chars:
        return text

    logger.warning(
        "⚠️ [Context] 텍스트가 토큰 제한을 초과하여 잘렸습니다 "
        "(원본: ~%d토큰, 제한: %d토큰)",
        estimate_token_count(text),
        max_tokens,
    )

    if keep == "tail":
        return "...[앞부분 생략]\n" + text[-max_chars:]
    return text[:max_chars] + "\n...[이하 생략]"
