import kuzu
import os
import shutil

class KuzuManager:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = "./database/speaknode.kuzu"
            
        # DB 경로의 상위 폴더 생성 (dirname이 빈 문자열일 때 방어)
        parent_dir = os.path.dirname(db_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
            
        self.db_path = db_path
        self.db = kuzu.Database(db_path)
        self.conn = kuzu.Connection(self.db)
        self._initialize_schema()

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
        Vector RAG를 위해 Utterance에 embedding 컬럼 추가
        """
        tables = {
            "NODE": [
                "Person(name STRING, role STRING, PRIMARY KEY(name))",
                "Topic(title STRING, summary STRING, PRIMARY KEY(title))",
                "Task(description STRING, deadline STRING, status STRING, PRIMARY KEY(description))",
                "Decision(description STRING, PRIMARY KEY(description))",
                # [New] 벡터 검색을 위한 embedding 컬럼 추가 (384차원: all-MiniLM-L6-v2 기준)
                "Utterance(id STRING, text STRING, startTime FLOAT, endTime FLOAT, embedding FLOAT[384], PRIMARY KEY(id))"
            ],
            "REL": [
                "PROPOSED(FROM Person TO Topic)",
                "ASSIGNED_TO(FROM Person TO Task)",
                "RESULTED_IN(FROM Topic TO Decision)",
                "SPOKE(FROM Person TO Utterance)",
                # [New] 대화의 흐름(순서)을 저장하기 위한 관계
                "NEXT(FROM Utterance TO Utterance)"
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

    def ingest_transcript(self, segments: list, embeddings: list = None):
        """
        [New] STT 결과(전체 대화 내용)를 DB에 적재
        - segments: Transcriber 결과 리스트
        - embeddings: 각 세그먼트에 대응하는 벡터 리스트 (Optional)
        """
        print(f"📥 [DB] 대화 내용 적재 시작 (총 {len(segments)} 문장)...")
        
        previous_id = None
        
        try:
            for i, seg in enumerate(segments):
                # 1. 고유 ID 생성 (Time 기반)
                # 시작 시간을 ID로 쓰면 유니크하고 정렬됨 (예: "u_0012.50")
                u_id = f"u_{seg['start']:08.2f}"
                text = seg['text']
                start = seg['start']
                end = seg['end']
                
                # 임베딩이 있으면 넣고, 없으면 0으로 채움 (나중에 업데이트 가능)
                vector = embeddings[i] if embeddings and i < len(embeddings) else [0.0] * 384
                
                # 2. Utterance 노드 생성
                self.conn.execute(
                    """
                    MERGE (u:Utterance {id: $id})
                    ON CREATE SET u.text = $text, u.startTime = $start, u.endTime = $end, u.embedding = $vec
                    ON MATCH SET u.text = $text, u.embedding = $vec
                    """,
                    {"id": u_id, "text": text, "start": start, "end": end, "vec": vector}
                )
                
                # 3. 화자(Speaker) 연결 (SPOKE)
                # 현재 STT에 화자 분리가 없으면 'Unknown'으로 처리
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
                
                previous_id = u_id
                
            print(f"✅ [DB] 대화 흐름(NEXT) 및 화자(SPOKE) 연결 완료.")
            
        except Exception as e:
            print(f"❌ 대화 내용 적재 중 오류: {e}")
            raise e

    def ingest_data(self, analysis_result: dict):
        """
        [Existing] LLM 분석 결과(요약, 할일 등) 적재
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