import logging
import os

import kuzu

from core.config import SpeakNodeConfig
from core.utils import normalize_task_status

logger = logging.getLogger(__name__)

SCOPED_VALUE_SEPARATOR = "::"


def build_scoped_value(meeting_id: str | None, value: str) -> str:
    """회의 단위 충돌 방지를 위한 스코프 키 생성."""
    clean = str(value or "").strip()
    if not clean:
        return ""
    if not meeting_id:
        return clean
    return f"{meeting_id}{SCOPED_VALUE_SEPARATOR}{clean}"


def decode_scoped_value(value: str) -> str:
    """스코프 키에서 사용자 표시용 원본 값을 추출."""
    raw = str(value or "")
    if SCOPED_VALUE_SEPARATOR not in raw:
        return raw
    _, plain = raw.split(SCOPED_VALUE_SEPARATOR, 1)
    return plain


def extract_scope_from_value(value: str) -> str:
    """스코프 키에서 meeting_id를 추출."""
    raw = str(value or "")
    if SCOPED_VALUE_SEPARATOR not in raw:
        return ""
    meeting_id, _ = raw.split(SCOPED_VALUE_SEPARATOR, 1)
    return meeting_id if meeting_id.startswith("m_") else ""


class KuzuManager:
    def __init__(self, db_path=None, config: SpeakNodeConfig = None):
        cfg = config or SpeakNodeConfig()
        if db_path is None:
            db_path = cfg.get_chat_db_path()
            
        # DB 경로의 상위 폴더 생성 (dirname이 빈 문자열일 때 방어)
        parent_dir = os.path.dirname(db_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
            
        self.db_path = db_path
        self.config = cfg
        self.db = kuzu.Database(db_path)
        self.conn = kuzu.Connection(self.db)
        self._initialize_schema()
        logger.debug("KuzuDB 연결 완료: %s", db_path)

    # --- Context Manager ---
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False  # 예외를 삼키지 않음

    def close(self):
        """DB 리소스를 명시적으로 해제하여 Lock 방지"""
        try:
            # Connection → Database 순서로 해제 (의존 순서 역순)
            if getattr(self, "conn", None) is not None:
                if hasattr(self.conn, "close"):
                    self.conn.close()
                self.conn = None
            if getattr(self, "db", None) is not None:
                if hasattr(self.db, "close"):
                    self.db.close()
                self.db = None
            logger.debug("💾 KuzuDB 리소스가 안전하게 해제되었습니다.")
        except Exception as e:
            logger.warning("⚠️ DB 해제 중 오류 발생: %s", e)

    def _initialize_schema(self):
        """
        스키마 정의 (Graph + Vector)
        Meeting 노드로 회의 단위 관리, Utterance에 embedding으로 Vector RAG 지원
        """
        dim = self.config.embedding_dim
        tables = {
            "NODE": [
                "Person(name STRING, role STRING, PRIMARY KEY(name))",
                "Topic(title STRING, summary STRING, PRIMARY KEY(title))",
                "Task(description STRING, deadline STRING, status STRING, PRIMARY KEY(description))",
                "Decision(description STRING, PRIMARY KEY(description))",
                f"Utterance(id STRING, text STRING, startTime FLOAT, endTime FLOAT, embedding FLOAT[{dim}], PRIMARY KEY(id))",
                "Meeting(id STRING, title STRING, date STRING, source_file STRING, PRIMARY KEY(id))",
            ],
            "REL": [
                "PROPOSED(FROM Person TO Topic)",
                "ASSIGNED_TO(FROM Person TO Task)",
                "RESULTED_IN(FROM Topic TO Decision)",
                "SPOKE(FROM Person TO Utterance)",
                "NEXT(FROM Utterance TO Utterance)",
                "DISCUSSED(FROM Meeting TO Topic)",
                "CONTAINS(FROM Meeting TO Utterance)",
                "HAS_TASK(FROM Meeting TO Task)",
                "HAS_DECISION(FROM Meeting TO Decision)",
            ]
        }
        
        for table_type, definitions in tables.items():
            for definition in definitions:
                try:
                    self.conn.execute(f"CREATE {table_type} TABLE {definition}")
                except Exception as e:
                    # 이미 존재하는 테이블 에러는 무시
                    if "already exists" not in str(e).lower():
                        logger.warning("⚠️ 스키마 생성 중 예외 발생 (%s): %s", definition, e)

    def ingest_transcript(self, segments: list, embeddings: list = None, meeting_id: str = None) -> int:
        """
        STT 결과(전체 대화 내용)를 DB에 적재
        - segments: Transcriber 결과 리스트
        - embeddings: 각 세그먼트에 대응하는 벡터 리스트 (Optional)
        - meeting_id: 회의 ID (있으면 Meeting-CONTAINS 연결)
        반환값: 성공적으로 적재된 세그먼트 수
        """
        logger.info("📥 [DB] 대화 내용 적재 시작 (총 %d 문장)...", len(segments))
        dim = self.config.embedding_dim
        previous_id = None
        ingested_count = 0
        
        # --- 임베딩 싱크 검증 ---
        if embeddings is not None and len(embeddings) != len(segments):
            logger.warning(
                "⚠️ [DB] 임베딩 길이 불일치! segments=%d, embeddings=%d. "
                "부족분은 제로벡터로 채워집니다 (Vector RAG 품질 저하 가능).",
                len(segments), len(embeddings),
            )
        
        try:
            for i, seg in enumerate(segments):
                # meeting_id + index 기반 식별자로 타임스탬프 충돌을 방지합니다.
                start = float(seg.get("start", 0.0))
                end = float(seg.get("end", 0.0))
                text = str(seg.get("text", "")).strip()
                scope = meeting_id or "global"
                u_id = f"u_{scope}_{i:06d}_{int(start * 1000):010d}"
                
                # 임베딩이 있으면 넣고, 없으면 0으로 채움
                vector = embeddings[i] if embeddings and i < len(embeddings) else [0.0] * dim
                
                self.conn.execute(
                    "MERGE (u:Utterance {id: $id}) ON CREATE SET u.text = $text, u.startTime = $stime, u.endTime = $etime, u.embedding = $vec",
                    {"id": u_id, "text": text, "stime": start, "etime": end, "vec": vector}
                )
                
                speaker_name = seg.get('speaker', 'Unknown')
                self.conn.execute(
                    "MERGE (p:Person {name: $name}) ON CREATE SET p.role = 'Member'",
                    {"name": speaker_name}
                )
                self.conn.execute(
                    "MATCH (p:Person {name: $name}), (u:Utterance {id: $id}) MERGE (p)-[:SPOKE]->(u)",
                    {"name": speaker_name, "id": u_id}
                )
                
                if previous_id:
                    self.conn.execute(
                        "MATCH (prev:Utterance {id: $pid}), (curr:Utterance {id: $cid}) MERGE (prev)-[:NEXT]->(curr)",
                        {"pid": previous_id, "cid": u_id}
                    )
                
                if meeting_id:
                    self.conn.execute(
                        "MATCH (m:Meeting {id: $mid}), (u:Utterance {id: $uid}) MERGE (m)-[:CONTAINS]->(u)",
                        {"mid": meeting_id, "uid": u_id}
                    )
                
                previous_id = u_id
                ingested_count += 1
                
            logger.info("✅ [DB] 대화 흐름(NEXT) 및 화자(SPOKE) 연결 완료. (%d/%d건 적재)", ingested_count, len(segments))

        except Exception:
            logger.exception("❌ 대화 내용 적재 중 오류 (적재 완료: %d/%d건)", ingested_count, len(segments))
            raise
        
        return ingested_count

    # ================================================================
    # 📦 Dump/Restore — PNG 공유용 전체 그래프 직렬화
    # ================================================================

    def export_graph_dump(self, include_embeddings: bool = True) -> dict:
        """현재 DB의 노드/엣지를 공유 가능한 JSON 덤프로 추출."""
        dump = {
            "schema_version": 2,
            "nodes": {
                "meetings": [],
                "people": [],
                "topics": [],
                "tasks": [],
                "decisions": [],
                "utterances": [],
            },
            "edges": {
                "proposed": [],
                "assigned_to": [],
                "resulted_in": [],
                "spoke": [],
                "next": [],
                "discussed": [],
                "contains": [],
                "has_task": [],
                "has_decision": [],
            },
        }

        # Nodes
        for r in self.execute_cypher("MATCH (m:Meeting) RETURN m.id, m.title, m.date, m.source_file"):
            dump["nodes"]["meetings"].append(
                {"id": r[0], "title": r[1], "date": r[2], "source_file": r[3]}
            )
        for r in self.execute_cypher("MATCH (p:Person) RETURN p.name, p.role"):
            dump["nodes"]["people"].append({"name": r[0], "role": r[1]})
        for r in self.execute_cypher("MATCH (t:Topic) RETURN t.title, t.summary"):
            dump["nodes"]["topics"].append({"title": r[0], "summary": r[1]})
        for r in self.execute_cypher("MATCH (t:Task) RETURN t.description, t.deadline, t.status"):
            dump["nodes"]["tasks"].append(
                {"description": r[0], "deadline": r[1], "status": r[2]}
            )
        for r in self.execute_cypher("MATCH (d:Decision) RETURN d.description"):
            dump["nodes"]["decisions"].append({"description": r[0]})
        if include_embeddings:
            utterance_rows = self.execute_cypher(
                "MATCH (u:Utterance) RETURN u.id, u.text, u.startTime, u.endTime, u.embedding"
            )
            for r in utterance_rows:
                dump["nodes"]["utterances"].append(
                    {"id": r[0], "text": r[1], "start": r[2], "end": r[3], "embedding": r[4]}
                )
        else:
            utterance_rows = self.execute_cypher(
                "MATCH (u:Utterance) RETURN u.id, u.text, u.startTime, u.endTime"
            )
            for r in utterance_rows:
                dump["nodes"]["utterances"].append(
                    {"id": r[0], "text": r[1], "start": r[2], "end": r[3]}
                )

        # Edges
        for r in self.execute_cypher(
            "MATCH (p:Person)-[:PROPOSED]->(t:Topic) RETURN p.name, t.title"
        ):
            dump["edges"]["proposed"].append({"person": r[0], "topic": r[1]})
        for r in self.execute_cypher(
            "MATCH (p:Person)-[:ASSIGNED_TO]->(t:Task) RETURN p.name, t.description"
        ):
            dump["edges"]["assigned_to"].append({"person": r[0], "task": r[1]})
        for r in self.execute_cypher(
            "MATCH (t:Topic)-[:RESULTED_IN]->(d:Decision) RETURN t.title, d.description"
        ):
            dump["edges"]["resulted_in"].append({"topic": r[0], "decision": r[1]})
        for r in self.execute_cypher(
            "MATCH (p:Person)-[:SPOKE]->(u:Utterance) RETURN p.name, u.id"
        ):
            dump["edges"]["spoke"].append({"person": r[0], "utterance_id": r[1]})
        for r in self.execute_cypher(
            "MATCH (a:Utterance)-[:NEXT]->(b:Utterance) RETURN a.id, b.id"
        ):
            dump["edges"]["next"].append({"from_utterance_id": r[0], "to_utterance_id": r[1]})
        for r in self.execute_cypher(
            "MATCH (m:Meeting)-[:DISCUSSED]->(t:Topic) RETURN m.id, t.title"
        ):
            dump["edges"]["discussed"].append({"meeting_id": r[0], "topic": r[1]})
        for r in self.execute_cypher(
            "MATCH (m:Meeting)-[:CONTAINS]->(u:Utterance) RETURN m.id, u.id"
        ):
            dump["edges"]["contains"].append({"meeting_id": r[0], "utterance_id": r[1]})
        for r in self.execute_cypher(
            "MATCH (m:Meeting)-[:HAS_TASK]->(t:Task) RETURN m.id, t.description"
        ):
            dump["edges"]["has_task"].append({"meeting_id": r[0], "task": r[1]})
        for r in self.execute_cypher(
            "MATCH (m:Meeting)-[:HAS_DECISION]->(d:Decision) RETURN m.id, d.description"
        ):
            dump["edges"]["has_decision"].append({"meeting_id": r[0], "decision": r[1]})

        return dump

    def restore_graph_dump(self, dump: dict) -> None:
        """export_graph_dump 결과를 DB에 복원."""
        if not isinstance(dump, dict):
            raise ValueError("graph dump must be a dict")

        nodes = dump.get("nodes", {})
        edges = dump.get("edges", {})

        # Nodes 복원
        for item in nodes.get("meetings", []):
            meeting_id = item.get("id", "")
            if not meeting_id:
                continue
            self.conn.execute(
                "MERGE (m:Meeting {id: $id}) SET m.title = $title, m.date = $date, m.source_file = $src",
                {
                    "id": meeting_id,
                    "title": item.get("title", ""),
                    "date": item.get("date", ""),
                    "src": item.get("source_file", ""),
                },
            )
        for item in nodes.get("people", []):
            person_name = item.get("name", "")
            if not person_name:
                continue
            self.conn.execute(
                "MERGE (p:Person {name: $name}) SET p.role = $role",
                {"name": person_name, "role": item.get("role", "Member")},
            )
        for item in nodes.get("topics", []):
            title = item.get("title", "")
            if not title:
                continue
            self.conn.execute(
                "MERGE (t:Topic {title: $title}) SET t.summary = $summary",
                {"title": title, "summary": item.get("summary", "")},
            )
        for item in nodes.get("tasks", []):
            desc = item.get("description", "")
            if not desc:
                continue
            self.conn.execute(
                "MERGE (t:Task {description: $desc}) SET t.deadline = $due, t.status = $status",
                {
                    "desc": desc,
                    "due": item.get("deadline", "TBD"),
                    "status": normalize_task_status(item.get("status", "pending")),
                },
            )
        for item in nodes.get("decisions", []):
            desc = item.get("description", "")
            if not desc:
                continue
            self.conn.execute(
                "MERGE (d:Decision {description: $desc})",
                {"desc": desc},
            )
        for item in nodes.get("utterances", []):
            utterance_id = item.get("id", "")
            if not utterance_id:
                continue
            self.conn.execute(
                "MERGE (u:Utterance {id: $id}) "
                "SET u.text = $text, u.startTime = $stime, u.endTime = $etime, u.embedding = $vec",
                {
                    "id": utterance_id,
                    "text": item.get("text", ""),
                    "stime": float(item.get("start", 0.0)),
                    "etime": float(item.get("end", 0.0)),
                    "vec": item.get("embedding", [0.0] * self.config.embedding_dim),
                },
            )

        # Edges 복원
        for item in edges.get("proposed", []):
            if not item.get("person") or not item.get("topic"):
                continue
            self.conn.execute(
                "MATCH (p:Person {name: $name}), (t:Topic {title: $title}) MERGE (p)-[:PROPOSED]->(t)",
                {"name": item.get("person", ""), "title": item.get("topic", "")},
            )
        for item in edges.get("assigned_to", []):
            if not item.get("person") or not item.get("task"):
                continue
            self.conn.execute(
                "MATCH (p:Person {name: $name}), (t:Task {description: $task}) MERGE (p)-[:ASSIGNED_TO]->(t)",
                {"name": item.get("person", ""), "task": item.get("task", "")},
            )
        for item in edges.get("resulted_in", []):
            if not item.get("topic") or not item.get("decision"):
                continue
            self.conn.execute(
                "MATCH (t:Topic {title: $title}), (d:Decision {description: $desc}) MERGE (t)-[:RESULTED_IN]->(d)",
                {"title": item.get("topic", ""), "desc": item.get("decision", "")},
            )
        for item in edges.get("spoke", []):
            if not item.get("person") or not item.get("utterance_id"):
                continue
            self.conn.execute(
                "MATCH (p:Person {name: $name}), (u:Utterance {id: $uid}) MERGE (p)-[:SPOKE]->(u)",
                {"name": item.get("person", ""), "uid": item.get("utterance_id", "")},
            )
        for item in edges.get("next", []):
            if not item.get("from_utterance_id") or not item.get("to_utterance_id"):
                continue
            self.conn.execute(
                "MATCH (a:Utterance {id: $a}), (b:Utterance {id: $b}) MERGE (a)-[:NEXT]->(b)",
                {"a": item.get("from_utterance_id", ""), "b": item.get("to_utterance_id", "")},
            )
        for item in edges.get("discussed", []):
            if not item.get("meeting_id") or not item.get("topic"):
                continue
            self.conn.execute(
                "MATCH (m:Meeting {id: $mid}), (t:Topic {title: $title}) MERGE (m)-[:DISCUSSED]->(t)",
                {"mid": item.get("meeting_id", ""), "title": item.get("topic", "")},
            )
        for item in edges.get("contains", []):
            if not item.get("meeting_id") or not item.get("utterance_id"):
                continue
            self.conn.execute(
                "MATCH (m:Meeting {id: $mid}), (u:Utterance {id: $uid}) MERGE (m)-[:CONTAINS]->(u)",
                {"mid": item.get("meeting_id", ""), "uid": item.get("utterance_id", "")},
            )
        for item in edges.get("has_task", []):
            if not item.get("meeting_id") or not item.get("task"):
                continue
            self.conn.execute(
                "MATCH (m:Meeting {id: $mid}), (t:Task {description: $task}) MERGE (m)-[:HAS_TASK]->(t)",
                {"mid": item.get("meeting_id", ""), "task": item.get("task", "")},
            )
        for item in edges.get("has_decision", []):
            if not item.get("meeting_id") or not item.get("decision"):
                continue
            self.conn.execute(
                "MATCH (m:Meeting {id: $mid}), (d:Decision {description: $desc}) MERGE (m)-[:HAS_DECISION]->(d)",
                {"mid": item.get("meeting_id", ""), "desc": item.get("decision", "")},
            )

    def ingest_data(self, analysis_result, meeting_id: str = None):
        """
        LLM 분석 결과(요약, 할일 등) 적재.
        analysis_result: dict 또는 AnalysisResult 모델 모두 허용.
        """
        # AnalysisResult Pydantic 모델 ↔ dict 역호환
        if hasattr(analysis_result, "to_dict"):
            analysis_result = analysis_result.to_dict()
        try:
            topic_keys_by_plain: dict[str, str] = {}

            # 1. Person 노드 (people 리스트가 있다면)
            for p in analysis_result.get("people", []):
                self.conn.execute(
                    "MERGE (p:Person {name: $name}) ON CREATE SET p.role = $role", 
                    {"name": p['name'], "role": p.get('role', 'Member')}
                )

            # 2. Topic 노드 및 관계
            for t in analysis_result.get("topics", []):
                plain_title = str(t.get("title", "")).strip()
                scoped_title = build_scoped_value(meeting_id, plain_title)
                if not scoped_title:
                    continue
                topic_keys_by_plain[plain_title] = scoped_title
                self.conn.execute(
                    "MERGE (t:Topic {title: $title}) ON CREATE SET t.summary = $summary",
                    {"title": scoped_title, "summary": t.get('summary', '')}
                )
                if t.get('proposer') and t['proposer'] != 'Unknown':
                    self.conn.execute(
                        "MATCH (p:Person {name: $name}), (t:Topic {title: $title}) MERGE (p)-[:PROPOSED]->(t)",
                        {"name": t['proposer'], "title": scoped_title}
                    )
                # Meeting ↔ Topic 연결 (DISCUSSED)
                if meeting_id:
                    self.conn.execute(
                        "MATCH (m:Meeting {id: $mid}), (t:Topic {title: $title}) MERGE (m)-[:DISCUSSED]->(t)",
                        {"mid": meeting_id, "title": scoped_title}
                    )

            # 3. Task 노드 및 관계
            for task in analysis_result.get("tasks", []):
                desc_text = str(task.get('description', '')).strip() or "No Description"
                scoped_desc = build_scoped_value(meeting_id, desc_text)
                status = normalize_task_status(task.get("status", "pending"))
                self.conn.execute(
                    "MERGE (t:Task {description: $task_desc}) "
                    "ON CREATE SET t.deadline = $due, t.status = $status",
                    {"task_desc": scoped_desc, "due": task.get('deadline', 'TBD'), "status": status}
                )
                if task.get('assignee') and task['assignee'] != 'Unassigned':
                    self.conn.execute(
                        "MERGE (p:Person {name: $name}) ON CREATE SET p.role = 'Member'",
                        {"name": task['assignee']},
                    )
                    self.conn.execute(
                        "MATCH (p:Person {name: $name}), (t:Task {description: $task_desc}) MERGE (p)-[:ASSIGNED_TO]->(t)",
                        {"name": task['assignee'], "task_desc": scoped_desc}
                    )
                if meeting_id:
                    self.conn.execute(
                        "MATCH (m:Meeting {id: $mid}), (t:Task {description: $task_desc}) MERGE (m)-[:HAS_TASK]->(t)",
                        {"mid": meeting_id, "task_desc": scoped_desc},
                    )

            # 4. Decision 노드 및 관계
            for d in analysis_result.get("decisions", []):
                desc_text = str(d.get('description', '')).strip() or "No Description"
                scoped_desc = build_scoped_value(meeting_id, desc_text)
                self.conn.execute("MERGE (d:Decision {description: $decision_desc})", {"decision_desc": scoped_desc})
                if meeting_id:
                    self.conn.execute(
                        "MATCH (m:Meeting {id: $mid}), (d:Decision {description: $decision_desc}) MERGE (m)-[:HAS_DECISION]->(d)",
                        {"mid": meeting_id, "decision_desc": scoped_desc},
                    )
                
                if d.get('related_topic'):
                    plain_related_topic = str(d.get("related_topic", "")).strip()
                    resolved_topic_key = topic_keys_by_plain.get(plain_related_topic)
                    if resolved_topic_key is None:
                        resolved_topic_key = build_scoped_value(meeting_id, plain_related_topic)
                    self.conn.execute(
                        "MATCH (t:Topic {title: $title}), (d:Decision {description: $decision_desc}) MERGE (t)-[:RESULTED_IN]->(d)",
                        {"title": resolved_topic_key, "decision_desc": scoped_desc}
                    )

            logger.info("🎉 지식 그래프(Knowledge Graph) 적재 완료!")
        except Exception:
            logger.exception("❌ 분석 데이터 적재 중 오류")
            raise

    # ================================================================
    # 🆕 Meeting (회의 단위 관리)
    # ================================================================

    def create_meeting(self, meeting_id: str, title: str, date: str = "", source_file: str = "") -> str:
        """
        Meeting 노드 생성 (회의 단위의 시작점)
        반환값: meeting_id
        """
        self.conn.execute(
            "MERGE (m:Meeting {id: $id}) ON CREATE SET m.title = $title, m.date = $date, m.source_file = $src",
            {"id": meeting_id, "title": title, "date": date, "src": source_file}
        )
        logger.info("📋 [DB] Meeting 생성: '%s' (%s)", title, meeting_id)
        return meeting_id

    # ================================================================
    # 📖 Graph RAG — 구조적 읽기/검색
    # ================================================================

    def execute_cypher(self, query: str, params: dict = None) -> list:
        """
        범용 Cypher 쿼리 실행. Agent가 직접 쿼리를 생성하여 호출할 수 있음.
        결과를 list[tuple]로 반환.
        """
        result = self.conn.execute(query, params or {})
        rows = []
        while result.has_next():
            rows.append(result.get_next())
        return rows

    def get_all_topics(self, limit: int = 20, keyword: str = "") -> list[dict]:
        """Topic 노드 조회 (선택적으로 keyword/limit 적용)."""
        if keyword:
            rows = self.execute_cypher(
                "MATCH (t:Topic) "
                "WHERE t.title CONTAINS $kw OR t.summary CONTAINS $kw "
                "RETURN t.title, t.summary LIMIT $lim",
                {"kw": keyword, "lim": limit},
            )
        else:
            rows = self.execute_cypher(
                "MATCH (t:Topic) RETURN t.title, t.summary LIMIT $lim",
                {"lim": limit},
            )
        return [
            {
                "id": r[0],
                "title": decode_scoped_value(r[0]),
                "summary": r[1],
                "meeting_id": extract_scope_from_value(r[0]),
            }
            for r in rows
        ]

    def get_all_tasks(self, limit: int = 20, keyword: str = "") -> list[dict]:
        """Task 노드 + 담당자 조회 (선택적으로 keyword/limit 적용)."""
        if keyword:
            rows = self.execute_cypher(
                "MATCH (t:Task) OPTIONAL MATCH (p:Person)-[:ASSIGNED_TO]->(t) "
                "WHERE t.description CONTAINS $kw OR t.status CONTAINS $kw OR p.name CONTAINS $kw "
                "RETURN t.description, t.deadline, t.status, p.name "
                "LIMIT $lim",
                {"kw": keyword, "lim": limit},
            )
        else:
            rows = self.execute_cypher(
                "MATCH (t:Task) OPTIONAL MATCH (p:Person)-[:ASSIGNED_TO]->(t) "
                "RETURN t.description, t.deadline, t.status, p.name "
                "LIMIT $lim",
                {"lim": limit},
            )
        return [{
            "id": r[0],
            "description": decode_scoped_value(r[0]),
            "deadline": r[1],
            "status": normalize_task_status(r[2]),
            "assignee": r[3],
            "meeting_id": extract_scope_from_value(r[0]),
        } for r in rows]

    def get_person_tasks(self, person_name: str, limit: int = 20) -> list[dict]:
        """특정 인물에게 할당된 Task 조회"""
        rows = self.execute_cypher(
            "MATCH (p:Person {name: $name})-[:ASSIGNED_TO]->(t:Task) "
            "RETURN t.description, t.deadline, t.status LIMIT $lim",
            {"name": person_name, "lim": limit},
        )
        return [{
            "id": r[0],
            "description": decode_scoped_value(r[0]),
            "deadline": r[1],
            "status": normalize_task_status(r[2]),
            "meeting_id": extract_scope_from_value(r[0]),
        } for r in rows]

    def get_topic_decisions(self, topic_title: str, limit: int = 20) -> list[dict]:
        """특정 Topic에서 도출된 Decision 조회"""
        target = (topic_title or "").strip()
        if not target:
            return []

        candidate_rows = self.execute_cypher(
            "MATCH (t:Topic) RETURN t.title LIMIT 5000"
        )
        matching_topic_keys = [
            row[0]
            for row in candidate_rows
            if row[0] == target or decode_scoped_value(row[0]) == target
        ]
        if not matching_topic_keys:
            return []

        decisions = []
        seen: set[str] = set()
        for topic_key in matching_topic_keys:
            rows = self.execute_cypher(
                "MATCH (t:Topic {title: $title})-[:RESULTED_IN]->(d:Decision) "
                "RETURN d.description LIMIT $lim",
                {"title": topic_key, "lim": limit},
            )
            for r in rows:
                raw_desc = r[0]
                if raw_desc in seen:
                    continue
                seen.add(raw_desc)
                decisions.append({
                    "id": raw_desc,
                    "description": decode_scoped_value(raw_desc),
                    "meeting_id": extract_scope_from_value(raw_desc),
                })
                if len(decisions) >= limit:
                    return decisions
        return decisions

    def get_all_people(self, limit: int = 20, keyword: str = "") -> list[dict]:
        """Person 노드 조회 (선택적으로 keyword/limit 적용)."""
        if keyword:
            rows = self.execute_cypher(
                "MATCH (p:Person) "
                "WHERE p.name CONTAINS $kw OR p.role CONTAINS $kw "
                "RETURN p.name, p.role LIMIT $lim",
                {"kw": keyword, "lim": limit},
            )
        else:
            rows = self.execute_cypher(
                "MATCH (p:Person) RETURN p.name, p.role LIMIT $lim",
                {"lim": limit},
            )
        return [{"name": r[0], "role": r[1]} for r in rows]

    def get_all_meetings(self, limit: int = 20, keyword: str = "") -> list[dict]:
        """Meeting 노드 조회 (선택적으로 keyword/limit 적용)."""
        if keyword:
            rows = self.execute_cypher(
                "MATCH (m:Meeting) "
                "WHERE m.title CONTAINS $kw OR m.date CONTAINS $kw OR m.source_file CONTAINS $kw "
                "RETURN m.id, m.title, m.date, m.source_file "
                "LIMIT $lim",
                {"kw": keyword, "lim": limit},
            )
        else:
            rows = self.execute_cypher(
                "MATCH (m:Meeting) RETURN m.id, m.title, m.date, m.source_file LIMIT $lim",
                {"lim": limit},
            )
        return [{"id": r[0], "title": r[1], "date": r[2], "source_file": r[3]} for r in rows]

    def get_meeting_summary(self, meeting_id: str) -> dict:
        """특정 회의의 전체 요약 (연결된 Topic, Task, Decision 포함)"""
        # 회의 기본 정보
        meeting_rows = self.execute_cypher(
            "MATCH (m:Meeting {id: $mid}) RETURN m.title, m.date, m.source_file",
            {"mid": meeting_id}
        )
        if not meeting_rows:
            return {}
        
        m = meeting_rows[0]
        # 연결된 Topic
        topics = self.execute_cypher(
            "MATCH (m:Meeting {id: $mid})-[:DISCUSSED]->(t:Topic) RETURN t.title, t.summary",
            {"mid": meeting_id}
        )
        decisions = self.execute_cypher(
            "MATCH (m:Meeting {id: $mid})-[:HAS_DECISION]->(d:Decision) "
            "RETURN DISTINCT d.description",
            {"mid": meeting_id},
        )
        if not decisions:
            # Legacy fallback: older DBs may not have HAS_DECISION edges.
            decisions = self.execute_cypher(
                "MATCH (m:Meeting {id: $mid})-[:DISCUSSED]->(:Topic)-[:RESULTED_IN]->(d:Decision) "
                "RETURN DISTINCT d.description",
                {"mid": meeting_id},
            )
        people = self.execute_cypher(
            "MATCH (m:Meeting {id: $mid})-[:CONTAINS]->(:Utterance)<-[:SPOKE]-(p:Person) "
            "RETURN DISTINCT p.name, p.role",
            {"mid": meeting_id},
        )
        tasks = self.execute_cypher(
            "MATCH (m:Meeting {id: $mid})-[:HAS_TASK]->(t:Task) "
            "OPTIONAL MATCH (p:Person)-[:ASSIGNED_TO]->(t) "
            "RETURN DISTINCT t.description, t.deadline, t.status, p.name",
            {"mid": meeting_id},
        )
        if not tasks:
            # Legacy fallback: older DBs may not have HAS_TASK edges.
            tasks = self.execute_cypher(
                "MATCH (m:Meeting {id: $mid})-[:CONTAINS]->(:Utterance)<-[:SPOKE]-(p:Person)-[:ASSIGNED_TO]->(t:Task) "
                "RETURN DISTINCT t.description, t.deadline, t.status, p.name",
                {"mid": meeting_id},
            )
        return {
            "meeting_id": meeting_id,
            "title": m[0], "date": m[1], "source_file": m[2],
            "topics": [
                {
                    "id": r[0],
                    "title": decode_scoped_value(r[0]),
                    "summary": r[1],
                    "meeting_id": extract_scope_from_value(r[0]),
                }
                for r in topics
            ],
            "decisions": [
                {
                    "id": r[0],
                    "description": decode_scoped_value(r[0]),
                    "meeting_id": extract_scope_from_value(r[0]),
                }
                for r in decisions
            ],
            "people": [{"name": r[0], "role": r[1]} for r in people],
            "tasks": [
                {
                    "id": r[0],
                    "description": decode_scoped_value(r[0]),
                    "deadline": r[1],
                    "status": normalize_task_status(r[2]),
                    "assignee": r[3],
                    "meeting_id": extract_scope_from_value(r[0]),
                }
                for r in tasks
            ],
        }

    # ================================================================
    # 🔍 Vector RAG — 의미 기반 검색
    # ================================================================

    def search_similar_utterances(self, query_vector: list, top_k: int = 5) -> list[dict]:
        """
        코사인 유사도 기반으로 가장 관련 있는 Utterance를 검색.
        DB에 벡터 인덱스가 없으면 순차 스캔으로 fallback.
        """
        try:
            # KuzuDB 0.11+ HNSW 벡터 검색 시도
            rows = self.execute_cypher(
                """
                MATCH (u:Utterance)
                WITH u, array_cosine_similarity(u.embedding, $qvec) AS score
                WHERE score > 0.0
                RETURN u.id, u.text, u.startTime, u.endTime, score
                ORDER BY score DESC
                LIMIT $k
                """,
                {"qvec": query_vector, "k": top_k}
            )
            return [{
                "id": r[0], "text": r[1],
                "start": r[2], "end": r[3], "score": r[4]
            } for r in rows]
        except Exception as e:
            logger.warning("⚠️ [Vector Search] 검색 실패: %s", e)
            return []
