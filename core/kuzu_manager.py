import kuzu
import os

class KuzuManager:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = "./database/speaknode.kuzu"
            
        if not os.path.exists(os.path.dirname(db_path)):
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            
        self.db = kuzu.Database(db_path)
        self.conn = kuzu.Connection(self.db)
        self._initialize_schema()

    def close(self):
        """DB 리소스를 명시적으로 해제하여 Lock 방지"""
        try:
            if getattr(self, "conn", None) is not None and hasattr(self.conn, "close"):
                self.conn.close()
            if getattr(self, "db", None) is not None and hasattr(self.db, "close"):
                self.db.close()

            self.conn = None
            self.db = None
            print("💾 KuzuDB 리소스가 안전하게 해제되었습니다.")
        except Exception as e:
            print(f"⚠️ DB 해제 중 오류 발생: {e}")

    def _initialize_schema(self):
        """스키마 생성 및 상세 예외 처리"""
        tables = {
            "NODE": [
                "Person(name STRING, role STRING, PRIMARY KEY(name))",
                "Topic(title STRING, summary STRING, PRIMARY KEY(title))",
                "Task(description STRING, deadline STRING, status STRING, PRIMARY KEY(description))",
                "Decision(description STRING, PRIMARY KEY(description))",
                "Utterance(id STRING, text STRING, startTime STRING, endTime STRING, PRIMARY KEY(id))"
            ],
            "REL": [
                "PROPOSED(FROM Person TO Topic)",
                "ASSIGNED_TO(FROM Person TO Task)",
                "RESULTED_IN(FROM Topic TO Decision)",
                "SPOKE(FROM Person TO Utterance)"
            ]
        }
        
        for table_type, definitions in tables.items():
            for definition in definitions:
                try:
                    self.conn.execute(f"CREATE {table_type} TABLE {definition}")
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        print(f"⚠️ 스키마 생성 중 예외 발생 ({definition}): {e}")

    def ingest_data(self, analysis_result: dict):
        """분석 결과를 그래프 DB에 적재 (관계 생성 포함)"""
        try:
            # 1. Person 노드
            for p in analysis_result.get("people", []):
                self.conn.execute(
                    "MERGE (p:Person {name: $name}) ON CREATE SET p.role = $role ON MATCH SET p.role = $role", 
                    {"name": p['name'], "role": p.get('role', 'Member')}
                )

            # 2. Topic 노드 및 관계
            for t in analysis_result.get("topics", []):
                self.conn.execute(
                    "MERGE (t:Topic {title: $title}) ON CREATE SET t.summary = $summary ON MATCH SET t.summary = $summary",
                    {"title": t['title'], "summary": t.get('summary', '')}
                )
                if 'proposer' in t:
                    self.conn.execute(
                        "MATCH (p:Person {name: $name}), (t:Topic {title: $title}) MERGE (p)-[:PROPOSED]->(t)",
                        {"name": t['proposer'], "title": t['title']}
                    )

            # 3. Task 노드 및 관계
            for task in analysis_result.get("tasks", []):
                desc_text = task.get('description', task.get('desc', 'No Description'))
                self.conn.execute(
                    "MERGE (t:Task {description: $task_desc}) ON CREATE SET t.deadline = $due, t.status = 'To Do' ON MATCH SET t.deadline = $due",
                    {"task_desc": desc_text, "due": task.get('deadline', 'TBD')}
                )
                if 'assignee' in task:
                    self.conn.execute(
                        "MATCH (p:Person {name: $name}), (t:Task {description: $task_desc}) MERGE (p)-[:ASSIGNED_TO]->(t)",
                        {"name": task['assignee'], "task_desc": desc_text}
                    )

            # 4. Decision 노드 및 관계 (Topic과 연결)
            for d in analysis_result.get("decisions", []):
                desc_text = d.get('description', d.get('desc', 'No Description'))
                self.conn.execute("MERGE (d:Decision {description: $decision_desc})", {"decision_desc": desc_text})
                
                # Decision이 특정 Topic과 연관되어 있다면 연결 (LLM 추출 구조에 따라 조정 가능)
                if 'related_topic' in d:
                    self.conn.execute(
                        "MATCH (t:Topic {title: $title}), (d:Decision {description: $decision_desc}) MERGE (t)-[:RESULTED_IN]->(d)",
                        {"title": d['related_topic'], "decision_desc": desc_text}
                    )

            print(f"🎉 데이터 적재 완료! (Topics: {len(analysis_result.get('topics', []))}개)")
        except Exception as e:
            print(f"❌ 데이터 적재 중 오류 발생: {e}")
            raise
