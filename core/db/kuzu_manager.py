import logging
import os
from contextlib import contextmanager

import kuzu

from core.config import SpeakNodeConfig
from core.utils import normalize_task_status

logger = logging.getLogger(__name__)

SCOPED_VALUE_SEPARATOR = "::"


def build_scoped_value(meeting_id: str | None, value: str) -> str:
    """Create a meeting-scoped key to prevent cross-meeting collisions."""
    clean = str(value or "").strip()
    if not clean:
        return ""
    if not meeting_id:
        return clean
    return f"{meeting_id}{SCOPED_VALUE_SEPARATOR}{clean}"


def decode_scoped_value(value: str) -> str:
    """Extract the plain display value from a scoped key."""
    raw = str(value or "")
    if SCOPED_VALUE_SEPARATOR not in raw:
        return raw
    _, plain = raw.split(SCOPED_VALUE_SEPARATOR, 1)
    return plain


def extract_scope_from_value(value: str) -> str:
    """Extract the meeting_id from a scoped key."""
    raw = str(value or "")
    if SCOPED_VALUE_SEPARATOR not in raw:
        return ""
    meeting_id, _ = raw.split(SCOPED_VALUE_SEPARATOR, 1)
    return meeting_id if meeting_id.startswith("m_") else ""


class KuzuManager:
    def __init__(self, db_path: str | None = None, config: SpeakNodeConfig | None = None):
        cfg = config or SpeakNodeConfig()
        if db_path is None:
            db_path = cfg.get_chat_db_path()
            
        # Create parent directory if needed
        parent_dir = os.path.dirname(db_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
            
        self.db_path = db_path
        self.config = cfg
        self.db = kuzu.Database(db_path)
        try:
            self.conn = kuzu.Connection(self.db)
            self._initialize_schema()
        except Exception:
            try:
                self.db.close()
            except Exception:
                pass
            raise
        logger.debug("KuzuDB connected: %s", db_path)

    # Context Manager 
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def close(self):
        """Release DB resources (Connection then Database)."""
        try:
            if getattr(self, "conn", None) is not None:
                if hasattr(self.conn, "close"):
                    self.conn.close()
                self.conn = None
            if getattr(self, "db", None) is not None:
                if hasattr(self.db, "close"):
                    self.db.close()
                self.db = None
            logger.debug("KuzuDB resources released.")
        except Exception as e:
            logger.warning("Error releasing DB resources: %s", e)

    @contextmanager
    def _transaction(self):
        """Manual transaction: wraps a block in BEGIN/COMMIT with ROLLBACK on error."""
        self.conn.execute("BEGIN TRANSACTION")
        try:
            yield
            self.conn.execute("COMMIT")
        except BaseException:
            try:
                self.conn.execute("ROLLBACK")
                logger.info("Transaction rolled back.")
            except Exception as rb_err:
                logger.error("ROLLBACK failed: %s", rb_err)
            raise

    def _initialize_schema(self):
        """Create node and relationship tables if they do not exist."""
        dim = self.config.embedding_dim
        tables = {
            "NODE": [
                "Person(name STRING, role STRING, PRIMARY KEY(name))",
                "Topic(title STRING, summary STRING, PRIMARY KEY(title))",
                "Task(description STRING, deadline STRING, status STRING, PRIMARY KEY(description))",
                "Decision(description STRING, PRIMARY KEY(description))",
                f"Utterance(id STRING, text STRING, startTime FLOAT, endTime FLOAT, embedding FLOAT[{dim}], PRIMARY KEY(id))",
                "Meeting(id STRING, title STRING, date STRING, source_file STRING, PRIMARY KEY(id))",
                "Entity(name STRING, entity_type STRING, description STRING, PRIMARY KEY(name))",
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
                "RELATED_TO(FROM Entity TO Entity, relation_type STRING)",
                "MENTIONS(FROM Topic TO Entity)",
                "HAS_ENTITY(FROM Meeting TO Entity)",
            ]
        }
        
        for table_type, definitions in tables.items():
            for definition in definitions:
                try:
                    self.conn.execute(f"CREATE {table_type} TABLE {definition}")
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        logger.warning("⚠️ 스키마 생성 중 예외 발생 (%s): %s", definition, e)

    def ingest_transcript(self, segments: list[dict], embeddings: list[list[float]] | None = None, meeting_id: str | None = None) -> int:
        """Ingest STT segments into the graph. Wrapped in a transaction."""
        logger.info("Ingesting %d segments...", len(segments))
        dim = self.config.embedding_dim
        previous_id = None
        ingested_count = 0
        
        # Validate embedding/segment count before entering transaction
        if embeddings is not None and len(embeddings) != len(segments):
            raise ValueError(
                f"Embedding count mismatch: segments={len(segments)}, embeddings={len(embeddings)}"
            )
        
        try:
            with self._transaction():
                for i, seg in enumerate(segments):
                    start = float(seg.get("start", 0.0))
                    end = float(seg.get("end", 0.0))
                    text = str(seg.get("text", "")).strip()
                    scope = meeting_id or "global"
                    u_id = f"u_{scope}_{i:06d}_{int(start * 1000):010d}"
                    
                    # Require an actual embedding for every segment
                    if not embeddings or i >= len(embeddings):
                        raise ValueError(
                            f"Missing embedding for segment {i}"
                        )
                    vector = embeddings[i]
                    
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
                
            logger.info("Transcript ingested (%d/%d segments).", ingested_count, len(segments))

        except Exception:
            logger.exception("Transcript ingest error (%d/%d done)", ingested_count, len(segments))
            raise
        
        return ingested_count

    def export_graph_dump(self, include_embeddings: bool = True) -> dict:
        """Serialize the full graph to a shareable JSON-compatible dict."""
        dump = {
            "schema_version": 3,
            "nodes": {
                "meetings": [],
                "people": [],
                "topics": [],
                "tasks": [],
                "decisions": [],
                "utterances": [],
                "entities": [],
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
                "related_to": [],
                "mentions": [],
                "has_entity": [],
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

        # Entity nodes (graceful fallback for old DBs)
        try:
            for r in self.execute_cypher("MATCH (e:Entity) RETURN e.name, e.entity_type, e.description"):
                dump["nodes"]["entities"].append(
                    {"name": r[0], "entity_type": r[1], "description": r[2]}
                )
            for r in self.execute_cypher(
                "MATCH (a:Entity)-[r:RELATED_TO]->(b:Entity) RETURN a.name, r.relation_type, b.name"
            ):
                dump["edges"]["related_to"].append(
                    {"source": r[0], "relation_type": r[1], "target": r[2]}
                )
            for r in self.execute_cypher(
                "MATCH (t:Topic)-[:MENTIONS]->(e:Entity) RETURN t.title, e.name"
            ):
                dump["edges"]["mentions"].append({"topic": r[0], "entity": r[1]})
            for r in self.execute_cypher(
                "MATCH (m:Meeting)-[:HAS_ENTITY]->(e:Entity) RETURN m.id, e.name"
            ):
                dump["edges"]["has_entity"].append({"meeting_id": r[0], "entity": r[1]})
        except Exception:
            # Old DB without Entity table — skip silently
            pass

        return dump

    def restore_graph_dump(self, dump: dict) -> None:
        """Restore a graph dump into the DB. Wrapped in a transaction."""
        if not isinstance(dump, dict):
            raise ValueError("graph dump must be a dict")

        nodes = dump.get("nodes", {})
        edges = dump.get("edges", {})

        has_embeddings_missing = False

        with self._transaction():
            # Nodes restore
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
                task_desc = item.get("description", "")
                if not task_desc:
                    continue
                self.conn.execute(
                    "MERGE (t:Task {description: $task_desc}) SET t.deadline = $due, t.status = $status",
                    {
                        "task_desc": task_desc,
                        "due": item.get("deadline", "TBD"),
                        "status": normalize_task_status(item.get("status", "pending")),
                    },
                )
            for item in nodes.get("decisions", []):
                decision_desc = item.get("description", "")
                if not decision_desc:
                    continue
                self.conn.execute(
                    "MERGE (d:Decision {description: $decision_desc})",
                    {"decision_desc": decision_desc},
                )
            for item in nodes.get("utterances", []):
                utterance_id = item.get("id", "")
                if not utterance_id:
                    continue
                embedding = item.get("embedding")
                if not embedding:
                    has_embeddings_missing = True
                    embedding = [0.0] * self.config.embedding_dim
                self.conn.execute(
                    "MERGE (u:Utterance {id: $id}) "
                    "SET u.text = $text, u.startTime = $stime, u.endTime = $etime, u.embedding = $vec",
                    {
                        "id": utterance_id,
                        "text": item.get("text", ""),
                        "stime": float(item.get("start", 0.0)),
                        "etime": float(item.get("end", 0.0)),
                        "vec": embedding,
                    },
                )

            # Edges resotre
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
                    "MATCH (t:Topic {title: $title}), (d:Decision {description: $decision_desc}) MERGE (t)-[:RESULTED_IN]->(d)",
                    {"title": item.get("topic", ""), "decision_desc": item.get("decision", "")},
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
                    "MATCH (m:Meeting {id: $mid}), (d:Decision {description: $decision_desc}) MERGE (m)-[:HAS_DECISION]->(d)",
                    {"mid": item.get("meeting_id", ""), "decision_desc": item.get("decision", "")},
                )

            # Entity nodes (schema_version >= 3, graceful skip for v2 dumps)
            for item in nodes.get("entities", []):
                ent_name = item.get("name", "")
                if not ent_name:
                    continue
                self.conn.execute(
                    "MERGE (e:Entity {name: $name}) ON CREATE SET e.entity_type = $etype, e.description = $desc",
                    {
                        "name": ent_name,
                        "etype": item.get("entity_type", "concept"),
                        "desc": item.get("description", ""),
                    },
                )
            for item in edges.get("related_to", []):
                if not item.get("source") or not item.get("target"):
                    continue
                self.conn.execute(
                    "MATCH (a:Entity {name: $src}), (b:Entity {name: $tgt}) "
                    "MERGE (a)-[:RELATED_TO {relation_type: $rtype}]->(b)",
                    {
                        "src": item.get("source", ""),
                        "tgt": item.get("target", ""),
                        "rtype": item.get("relation_type", "related_to"),
                    },
                )
            for item in edges.get("mentions", []):
                if not item.get("topic") or not item.get("entity"):
                    continue
                self.conn.execute(
                    "MATCH (t:Topic {title: $ttitle}), (e:Entity {name: $ename}) MERGE (t)-[:MENTIONS]->(e)",
                    {"ttitle": item.get("topic", ""), "ename": item.get("entity", "")},
                )
            for item in edges.get("has_entity", []):
                if not item.get("meeting_id") or not item.get("entity"):
                    continue
                self.conn.execute(
                    "MATCH (m:Meeting {id: $mid}), (e:Entity {name: $ename}) MERGE (m)-[:HAS_ENTITY]->(e)",
                    {"mid": item.get("meeting_id", ""), "ename": item.get("entity", "")},
                )

        if has_embeddings_missing:
            logger.warning(
                "Some utterances had no embeddings and were restored with zero vectors. "
                "Vector search quality may be reduced."
            )

    def ingest_data(self, analysis_result: dict, meeting_id: str | None = None) -> None:
        """Ingest LLM-extracted analysis data. Wrapped in a transaction."""
        # AnalysisResult Pydantic model <-> dict compatibility
        if hasattr(analysis_result, "to_dict"):
            analysis_result = analysis_result.to_dict()
        try:
            with self._transaction():
                topic_keys_by_plain: dict[str, str] = {}

                # Person node
                for p in analysis_result.get("people", []):
                    self.conn.execute(
                        "MERGE (p:Person {name: $name}) ON CREATE SET p.role = $role", 
                        {"name": p['name'], "role": p.get('role', 'Member')}
                    )

                # Topic node and relationship
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
                    # Meeting ↔ Topic connect
                    if meeting_id:
                        self.conn.execute(
                            "MATCH (m:Meeting {id: $mid}), (t:Topic {title: $title}) MERGE (m)-[:DISCUSSED]->(t)",
                            {"mid": meeting_id, "title": scoped_title}
                        )

                # Task node and relationship
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

                # Decision node and relationship
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

                # Entity node and relationships
                entity_keys_by_plain: dict[str, str] = {}
                for ent in analysis_result.get("entities", []):
                    ent_name = str(ent.get("name", "")).strip()
                    if not ent_name:
                        continue
                    scoped_name = build_scoped_value(meeting_id, ent_name)
                    entity_keys_by_plain[ent_name] = scoped_name
                    ent_type = str(ent.get("entity_type", "concept")).strip()
                    ent_desc = str(ent.get("description", "")).strip()
                    self.conn.execute(
                        "MERGE (e:Entity {name: $name}) ON CREATE SET e.entity_type = $etype, e.description = $desc",
                        {"name": scoped_name, "etype": ent_type, "desc": ent_desc},
                    )
                    # Meeting ↔ Entity connect
                    if meeting_id:
                        self.conn.execute(
                            "MATCH (m:Meeting {id: $mid}), (e:Entity {name: $ename}) MERGE (m)-[:HAS_ENTITY]->(e)",
                            {"mid": meeting_id, "ename": scoped_name},
                        )
                    # Also create Person node for person-type entities
                    if ent_type == "person":
                        self.conn.execute(
                            "MERGE (p:Person {name: $name}) ON CREATE SET p.role = 'Member'",
                            {"name": ent_name},
                        )

                # Entity-Entity relations
                for rel in analysis_result.get("relations", []):
                    src = str(rel.get("source", "")).strip()
                    tgt = str(rel.get("target", "")).strip()
                    rel_type = str(rel.get("relation_type", "related_to")).strip()
                    src_key = entity_keys_by_plain.get(src)
                    tgt_key = entity_keys_by_plain.get(tgt)
                    if not src_key or not tgt_key:
                        continue
                    self.conn.execute(
                        "MATCH (a:Entity {name: $src}), (b:Entity {name: $tgt}) "
                        "MERGE (a)-[:RELATED_TO {relation_type: $rtype}]->(b)",
                        {"src": src_key, "tgt": tgt_key, "rtype": rel_type},
                    )

                # Topic ↔ Entity connections (MENTIONS)
                for plain_title, scoped_title in topic_keys_by_plain.items():
                    topic_data = next(
                        (t for t in analysis_result.get("topics", [])
                         if str(t.get("title", "")).strip() == plain_title),
                        None,
                    )
                    if not topic_data:
                        continue
                    topic_text = f"{plain_title} {topic_data.get('summary', '')}"
                    for ent_plain, ent_scoped in entity_keys_by_plain.items():
                        if ent_plain in topic_text:
                            self.conn.execute(
                                "MATCH (t:Topic {title: $ttitle}), (e:Entity {name: $ename}) "
                                "MERGE (t)-[:MENTIONS]->(e)",
                                {"ttitle": scoped_title, "ename": ent_scoped},
                            )

            logger.info("Knowledge graph ingested.")
        except Exception:
            logger.exception("Analysis data ingest error")
            raise

    def create_meeting(self, meeting_id: str, title: str, date: str = "", source_file: str = "") -> str:
        """Create a Meeting node."""
        self.conn.execute(
            "MERGE (m:Meeting {id: $id}) ON CREATE SET m.title = $title, m.date = $date, m.source_file = $src",
            {"id": meeting_id, "title": title, "date": date, "src": source_file}
        )
        logger.info("Meeting created: '%s' (%s)", title, meeting_id)
        return meeting_id

    def execute_cypher(self, query: str, params: dict | None = None) -> list[tuple]:
        """Execute a Cypher query and return rows as list[tuple]."""
        result = self.conn.execute(query, params or {})
        rows: list[tuple] = []
        while result.has_next():
            rows.append(result.get_next())
        return rows

    def get_all_topics(self, limit: int = 20, keyword: str = "") -> list[dict]:
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

    def get_all_entities(self, limit: int = 20, keyword: str = "", entity_type: str = "") -> list[dict]:
        """Retrieve Entity nodes with optional keyword and type filter."""
        if keyword and entity_type:
            rows = self.execute_cypher(
                "MATCH (e:Entity) "
                "WHERE (e.name CONTAINS $kw OR e.description CONTAINS $kw) AND e.entity_type = $etype "
                "RETURN e.name, e.entity_type, e.description LIMIT $lim",
                {"kw": keyword, "etype": entity_type, "lim": limit},
            )
        elif keyword:
            rows = self.execute_cypher(
                "MATCH (e:Entity) "
                "WHERE e.name CONTAINS $kw OR e.description CONTAINS $kw "
                "RETURN e.name, e.entity_type, e.description LIMIT $lim",
                {"kw": keyword, "lim": limit},
            )
        elif entity_type:
            rows = self.execute_cypher(
                "MATCH (e:Entity) WHERE e.entity_type = $etype "
                "RETURN e.name, e.entity_type, e.description LIMIT $lim",
                {"etype": entity_type, "lim": limit},
            )
        else:
            rows = self.execute_cypher(
                "MATCH (e:Entity) RETURN e.name, e.entity_type, e.description LIMIT $lim",
                {"lim": limit},
            )
        return [
            {
                "name": decode_scoped_value(r[0]),
                "entity_type": r[1],
                "description": r[2],
                "meeting_id": extract_scope_from_value(r[0]),
            }
            for r in rows
        ]

    def get_entity_relations(self, entity_name: str = "", limit: int = 20) -> list[dict]:
        """Retrieve RELATED_TO edges, optionally filtered by entity name."""
        if entity_name:
            rows = self.execute_cypher(
                "MATCH (a:Entity)-[r:RELATED_TO]->(b:Entity) "
                "WHERE a.name CONTAINS $kw OR b.name CONTAINS $kw "
                "RETURN a.name, r.relation_type, b.name LIMIT $lim",
                {"kw": entity_name, "lim": limit},
            )
        else:
            rows = self.execute_cypher(
                "MATCH (a:Entity)-[r:RELATED_TO]->(b:Entity) "
                "RETURN a.name, r.relation_type, b.name LIMIT $lim",
                {"lim": limit},
            )
        return [
            {
                "source": decode_scoped_value(r[0]),
                "relation_type": r[1],
                "target": decode_scoped_value(r[2]),
            }
            for r in rows
        ]

    def get_meeting_summary(self, meeting_id: str) -> dict:
        # Meeting info
        meeting_rows = self.execute_cypher(
            "MATCH (m:Meeting {id: $mid}) RETURN m.title, m.date, m.source_file",
            {"mid": meeting_id}
        )
        if not meeting_rows:
            return {}
        
        m = meeting_rows[0]
        # Connected topics
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
        # Entities connected to this meeting (graceful fallback for old DBs)
        try:
            entities = self.execute_cypher(
                "MATCH (m:Meeting {id: $mid})-[:HAS_ENTITY]->(e:Entity) "
                "RETURN e.name, e.entity_type, e.description",
                {"mid": meeting_id},
            )
        except Exception:
            entities = []
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
            "entities": [
                {
                    "name": decode_scoped_value(r[0]),
                    "entity_type": r[1],
                    "description": r[2],
                    "meeting_id": extract_scope_from_value(r[0]),
                }
                for r in entities
            ],
        }

    def search_similar_utterances(self, query_vector: list[float], top_k: int = 5) -> list[dict]:
        """Cosine similarity search over utterance embeddings."""
        try:
            # KuzuDB 0.11+ HNSW Vector search attempt
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
