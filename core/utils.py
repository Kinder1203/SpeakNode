"""Shared business logic used across multiple modules."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Task status normalisation 

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
    """Normalize various status strings to one of the allowed values."""
    status = str(raw or "").strip().lower()
    normalized = _TASK_STATUS_ALIASES.get(status, status)
    return normalized if normalized in ALLOWED_TASK_STATUSES else "pending"


# LLM context window helpers 

# Conservative estimate: ~2 chars/token for mixed Korean/English text.
_CHARS_PER_TOKEN_ESTIMATE = 2

# Default max context tokens (Qwen2.5 14B: 32K minus ~4K for response)
DEFAULT_MAX_CONTEXT_TOKENS = 28_000


def estimate_token_count(text: str) -> int:
    return len(text) // _CHARS_PER_TOKEN_ESTIMATE


def truncate_text(
    text: str,
    max_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
    *,
    keep: str = "head",
) -> str:
    """Truncate text to stay within a token budget."""
    if not text:
        return text
    max_chars = max_tokens * _CHARS_PER_TOKEN_ESTIMATE
    if len(text) <= max_chars:
        return text

    logger.warning(
        "Text truncated (original ~%d tokens, limit %d tokens)",
        estimate_token_count(text),
        max_tokens,
    )

    if keep == "tail":
        return "...[truncated]\n" + text[-max_chars:]
    return text[:max_chars] + "\n...[truncated]"
