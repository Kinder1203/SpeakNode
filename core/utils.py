"""
SpeakNode 공통 유틸리티
========================
여러 모듈에서 공유되는 비즈니스 로직을 단일 소스로 관리합니다.
중복 정의를 방지하고, 변경 시 한 곳만 수정하면 됩니다.
"""

from __future__ import annotations

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
