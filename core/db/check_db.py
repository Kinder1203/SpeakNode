"""DB diagnostic script.

Usage:
    python -m core.db.check_db [meeting_id]
"""

from __future__ import annotations

import os
import sys

from core.config import SpeakNodeConfig, get_meeting_db_path, list_meeting_ids
from core.db.kuzu_manager import KuzuManager

_NODE_TABLES = ["Person", "Topic", "Task", "Decision", "Utterance", "Meeting", "Entity"]


def check_database(meeting_id: str | None = None) -> None:
    config = SpeakNodeConfig()

    if meeting_id:
        _check_single(meeting_id, config)
    else:
        ids = list_meeting_ids(config)
        if not ids:
            print("등록된 회의 DB가 없습니다.")
            return
        for mid in sorted(ids):
            _check_single(mid, config)
            print()


def _check_single(meeting_id: str, config: SpeakNodeConfig) -> None:
    db_path = get_meeting_db_path(meeting_id, config)
    print(f"=== Meeting: {meeting_id} ===")
    print(f"    경로: {db_path}")

    if not os.path.exists(db_path):
        print("    ❌ DB 파일/폴더가 존재하지 않습니다.")
        return

    try:
        with KuzuManager(db_path=db_path, config=config) as db:
            print("    ✅ DB 연결 성공")

            # List tables.
            print("\n    --- 테이블 목록 ---")
            for row in db.execute_cypher("CALL show_tables() RETURN *"):
                print(f"        📄 {row}")

            # Count nodes by label.
            print("\n    --- 노드 카운트 ---")
            for table in _NODE_TABLES:
                try:
                    rows = db.execute_cypher(f"MATCH (n:{table}) RETURN count(n)")
                    count = rows[0][0] if rows else 0
                    print(f"        📊 {table}: {count}개")
                except Exception:
                    pass

            # Show sample Topic rows.
            print("\n    --- Topic 데이터 ---")
            topics = db.execute_cypher("MATCH (t:Topic) RETURN t.title, t.summary")
            if not topics:
                print("        (저장된 Topic이 없습니다.)")
            for row in topics:
                print(f"        📌 제목: {row[0]}")
                print(f"        📝 요약: {row[1] or '(내용 없음)'}")
    except Exception as exc:
        print(f"    ❌ 오류: {exc}")


if __name__ == "__main__":
    _target = sys.argv[1] if len(sys.argv) > 1 else None
    check_database(meeting_id=_target)
