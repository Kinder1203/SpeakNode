# draft meeting follow-up emails.

from __future__ import annotations

import json
from core.agent.tools import default_registry as registry


@registry.register(
    "draft_email",
    "회의 결과를 바탕으로 이메일 초안을 작성합니다. 인자: recipient(str), subject(str)."
)
def draft_email(args: dict, db, rag) -> str:
    recipient = args.get("recipient", "")
    subject = args.get("subject", "회의 결과 공유")

    search_result = rag.hybrid_search(subject, db, top_k=3)
    context = search_result.get("merged_context", "")

    return json.dumps({
        "type": "email_draft_request",
        "recipient": recipient,
        "subject": subject,
        "context": context,
    }, ensure_ascii=False)
