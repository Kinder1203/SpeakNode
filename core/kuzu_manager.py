import kuzu
import os
import shutil
from core.config import SpeakNodeConfig

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
                self.conn = None
            if getattr(self, "db", None) is not None:
                self.db = None
            print("💾 KuzuDB 리소스가 안전하게 해제되었습니다.")
        except Exception as e:
            print(f"⚠️ DB 해제 중 오류 발생: {e}")

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
                # [New] 회의 단위 관리를 위한 Meeting 노드
                "Meeting(id STRING, title STRING, date STRING, source_file STRING, PRIMARY KEY(id))",
            ],
            "REL": [
                "PROPOSED(FROM Person TO Topic)",
                "ASSIGNED_TO(FROM Person TO Task)",
                "RESULTED_IN(FROM Topic TO Decision)",
                "SPOKE(FROM Person TO Utterance)",
                "NEXT(FROM Utterance TO Utterance)",
                # [New] 회의 ↔ 콘텐츠 연결
                "DISCUSSED(FROM Meeting TO Topic)",
                "CONTAINS(FROM Meeting TO Utterance)",
            ]
        }
        
        for table_type, definitions in tables.items():
            for definition in definitions:
                try:
                    self.conn.execute(f"CREATE {table_type} TABLE {definition}")
                except Exception as e:
                    # 이미 존재하는 테이블 에러는 무시
                    if "already exists" not in str(e).lower():
                        print(f"⚠️ 스키마 생성 중 예외 발생 ({definition}): {e}")

    def ingest_transcript(self, segments: list, embeddings: list = None, meeting_id: str = None) -> int:
        """
        STT 결과(전체 대화 내용)를 DB에 적재
        - segments: Transcriber 결과 리스트
        - embeddings: 각 세그먼트에 대응하는 벡터 리스트 (Optional)
        - meeting_id: 회의 ID (있으면 Meeting-CONTAINS 연결)
        반환값: 성공적으로 적재된 세그먼트 수
        """
        print(f"📥 [DB] 대화 내용 적재 시작 (총 {len(segments)} 문장)...")
        dim = self.config.embedding_dim
        previous_id = None
        ingested_count = 0
        
        # --- 임베딩 싱크 검증 ---
        if embeddings is not None and len(embeddings) != len(segments):
            print(f"⚠️ [DB] 임베딩 길이 불일치! segments={len(segments)}, embeddings={len(embeddings)}. "
                  f"부족분은 제로벡터로 채워집니다 (Vector RAG 품질 저하 가능).")
        
        try:
            for i, seg in enumerate(segments):
                # 1. 고유 ID 생성 (Time 기반)
                u_id = f"u_{seg['start']:08.2f}"
                text = seg['text']
                start = seg['start']
                end = seg['end']
                
                # 임베딩이 있으면 넣고, 없으면 0으로 채움
                vector = embeddings[i] if embeddings and i < len(embeddings) else [0.0] * dim
                
                # 2. Utterance 노드 생성 ($end → $etime: Cypher 예약어 충돌 방지)
                self.conn.execute(
                    "MERGE (u:Utterance {id: $id}) ON CREATE SET u.text = $text, u.startTime = $stime, u.endTime = $etime, u.embedding = $vec",
                    {"id": u_id, "text": text, "stime": start, "etime": end, "vec": vector}
                )
                
                # 3. 화자(Speaker) 연결 (SPOKE)
                speaker_name = seg.get('speaker', 'Unknown')
                self.conn.execute(
                    "MERGE (p:Person {name: $name}) ON CREATE SET p.role = 'Member'",
                    {"name": speaker_name}
                )
                self.conn.execute(
                    "MATCH (p:Person {name: $name}), (u:Utterance {id: $id}) MERGE (p)-[:SPOKE]->(u)",
                    {"name": speaker_name, "id": u_id}
                )
                
                # 4. 순서 연결 (NEXT)
                if previous_id:
                    self.conn.execute(
                        "MATCH (prev:Utterance {id: $pid}), (curr:Utterance {id: $cid}) MERGE (prev)-[:NEXT]->(curr)",
                        {"pid": previous_id, "cid": u_id}
                    )
                
                # 5. Meeting 연결 (CONTAINS)
                if meeting_id:
                    self.conn.execute(
                        "MATCH (m:Meeting {id: $mid}), (u:Utterance {id: $uid}) MERGE (m)-[:CONTAINS]->(u)",
                        {"mid": meeting_id, "uid": u_id}
                    )
                
                previous_id = u_id
                ingested_count += 1
                
            print(f"✅ [DB] 대화 흐름(NEXT) 및 화자(SPOKE) 연결 완료. ({ingested_count}/{len(segments)}건 적재)")
            
        except Exception as e:
            print(f"❌ 대화 내용 적재 중 오류 (적재 완료: {ingested_count}/{len(segments)}건): {e}")
            raise e
        
        return ingested_count

    def ingest_data(self, analysis_result: dict, meeting_id: str = None):
        """
        LLM 분석 결과(요약, 할일 등) 적재
        - meeting_id: 있으면 Topic을 Meeting에 DISCUSSED로 연결
        """
        try:
            # 1. Person 노드 (people 리스트가 있다면)
            for p in analysis_result.get("people", []):
                self.conn.execute(
                    "MERGE (p:Person {name: $name}) ON CREATE SET p.role = $role", 
                    {"name": p['name'], "role": p.get('role', 'Member')}
                )

            # 2. Topic 노드 및 관계
            for t in analysis_result.get("topics", []):
                self.conn.execute(
                    "MERGE (t:Topic {title: $title}) ON CREATE SET t.summary = $summary",
                    {"title": t['title'], "summary": t.get('summary', '')}
                )
                if t.get('proposer') and t['proposer'] != 'Unknown':
                    self.conn.execute(
                        "MATCH (p:Person {name: $name}), (t:Topic {title: $title}) MERGE (p)-[:PROPOSED]->(t)",
                        {"name": t['proposer'], "title": t['title']}
                    )
                # Meeting ↔ Topic 연결 (DISCUSSED)
                if meeting_id:
                    self.conn.execute(
                        "MATCH (m:Meeting {id: $mid}), (t:Topic {title: $title}) MERGE (m)-[:DISCUSSED]->(t)",
                        {"mid": meeting_id, "title": t['title']}
                    )

            # 3. Task 노드 및 관계
            for task in analysis_result.get("tasks", []):
                desc_text = task.get('description', 'No Description')
                self.conn.execute(
                    "MERGE (t:Task {description: $task_desc}) ON CREATE SET t.deadline = $due, t.status = 'To Do'",
                    {"task_desc": desc_text, "due": task.get('deadline', 'TBD')}
                )
                if task.get('assignee') and task['assignee'] != 'Unassigned':
                    self.conn.execute(
                        "MATCH (p:Person {name: $name}), (t:Task {description: $task_desc}) MERGE (p)-[:ASSIGNED_TO]->(t)",
                        {"name": task['assignee'], "task_desc": desc_text}
                    )

            # 4. Decision 노드 및 관계
            for d in analysis_result.get("decisions", []):
                desc_text = d.get('description', 'No Description')
                self.conn.execute("MERGE (d:Decision {description: $decision_desc})", {"decision_desc": desc_text})
                
                if d.get('related_topic'):
                    self.conn.execute(
                        "MATCH (t:Topic {title: $title}), (d:Decision {description: $decision_desc}) MERGE (t)-[:RESULTED_IN]->(d)",
                        {"title": d['related_topic'], "decision_desc": desc_text}
                    )

            print(f"🎉 지식 그래프(Knowledge Graph) 적재 완료!")
        except Exception as e:
            print(f"❌ 분석 데이터 적재 중 오류: {e}")
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
        print(f"📋 [DB] Meeting 생성: '{title}' ({meeting_id})")
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

    def get_all_topics(self) -> list[dict]:
        """모든 Topic 노드 조회"""
        rows = self.execute_cypher("MATCH (t:Topic) RETURN t.title, t.summary")
        return [{"title": r[0], "summary": r[1]} for r in rows]

    def get_all_tasks(self) -> list[dict]:
        """모든 Task 노드 + 담당자 조회"""
        rows = self.execute_cypher(
            "MATCH (t:Task) OPTIONAL MATCH (p:Person)-[:ASSIGNED_TO]->(t) "
            "RETURN t.description, t.deadline, t.status, p.name"
        )
        return [{
            "description": r[0], "deadline": r[1],
            "status": r[2], "assignee": r[3]
        } for r in rows]

    def get_person_tasks(self, person_name: str) -> list[dict]:
        """특정 인물에게 할당된 Task 조회"""
        rows = self.execute_cypher(
            "MATCH (p:Person {name: $name})-[:ASSIGNED_TO]->(t:Task) RETURN t.description, t.deadline, t.status",
            {"name": person_name}
        )
        return [{"description": r[0], "deadline": r[1], "status": r[2]} for r in rows]

    def get_topic_decisions(self, topic_title: str) -> list[dict]:
        """특정 Topic에서 도출된 Decision 조회"""
        rows = self.execute_cypher(
            "MATCH (t:Topic {title: $title})-[:RESULTED_IN]->(d:Decision) RETURN d.description",
            {"title": topic_title}
        )
        return [{"description": r[0]} for r in rows]

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
        return {
            "meeting_id": meeting_id,
            "title": m[0], "date": m[1], "source_file": m[2],
            "topics": [{"title": r[0], "summary": r[1]} for r in topics],
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
            print(f"⚠️ [Vector Search] 검색 실패: {e}")
            return []