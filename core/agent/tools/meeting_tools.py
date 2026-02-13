"""
회의 관련 도구: Meeting Summary
"""

from __future__ import annotations

import json
from core.agent.tools import default_registry as registry


@registry.register(
    "get_meeting_summary",
    "특정 회의의 전체 요약. 인자: meeting_id(str, 빈 문자열이면 전체 목록 반환)."
)
def get_meeting_summary(args: dict, db, rag) -> str:
    meeting_id = args.get("meeting_id", "")
    if not meeting_id:
        meetings = rag.graph_search_meetings(db)
        if not meetings:
            return "등록된 회의가 없습니다."
        return "회의 목록:\n" + "\n".join(
            f"- [{m['id']}] {m['title']} ({m.get('date', '')})" for m in meetings
        )
    summary = db.get_meeting_summary(meeting_id)
    if not summary:
        return f"회의 '{meeting_id}'를 찾을 수 없습니다."
    return json.dumps(summary, ensure_ascii=False, indent=2)
