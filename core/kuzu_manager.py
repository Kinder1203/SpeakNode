import kuzu
import os
import shutil

class KuzuManager:
    def __init__(self, db_path=None):
        if db_path is None:
            # fallback (테스트용)
            db_path = "./database/speaknode.kuzu"
            
        # 경로 생성
        if not os.path.exists(os.path.dirname(db_path)):
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            
        self.db = kuzu.Database(db_path)
        self.conn = kuzu.Connection(self.db)
        self._initialize_schema()

    def _initialize_schema(self):
        """스키마가 없을 때만 테이블 생성"""
        try:
            # Node: Person, Topic, Task, Decision, Utterance
            # desc는 예약어라 description으로 변경됨
            self.conn.execute("CREATE NODE TABLE Person(name STRING, role STRING, PRIMARY KEY(name))")
            self.conn.execute("CREATE NODE TABLE Topic(title STRING, summary STRING, PRIMARY KEY(title))")
            self.conn.execute("CREATE NODE TABLE Task(description STRING, deadline STRING, status STRING, PRIMARY KEY(description))")
            self.conn.execute("CREATE NODE TABLE Decision(description STRING, PRIMARY KEY(description))")
            self.conn.execute("CREATE NODE TABLE Utterance(id STRING, text STRING, startTime STRING, endTime STRING, PRIMARY KEY(id))")

            # Edge: 관계 정의
            self.conn.execute("CREATE REL TABLE PROPOSED(FROM Person TO Topic)")
            self.conn.execute("CREATE REL TABLE ASSIGNED_TO(FROM Person TO Task)")
            self.conn.execute("CREATE REL TABLE RESULTED_IN(FROM Topic TO Decision)")
            self.conn.execute("CREATE REL TABLE SPOKE(FROM Person TO Utterance)")
            print("✅ KuzuDB 스키마 초기화 완료")
        except Exception as e:
            # 이미 테이블이 존재하면 패스
            if "already exists" not in str(e):
                print(f"⚠️ 스키마 초기화 주의: {e}")

    def ingest_data(self, analysis_result: dict):
        """
        LLM 분석 결과(JSON)를 그래프 DB에 적재 (Upsert 방식 적용)
        """
        try:
            # 1. Person 노드 (이름으로 찾고, 역할은 업데이트)
            for p in analysis_result.get("people", []):
                self.conn.execute(
                    """
                    MERGE (p:Person {name: $name})
                    ON CREATE SET p.role = $role
                    ON MATCH SET p.role = $role
                    """, 
                    {"name": p['name'], "role": p.get('role', 'Member')}
                )

            # 2. Topic 노드 (제목으로 찾고, 요약은 업데이트) - 여기가 에러 났던 곳!
            for t in analysis_result.get("topics", []):
                self.conn.execute(
                    """
                    MERGE (t:Topic {title: $title})
                    ON CREATE SET t.summary = $summary
                    ON MATCH SET t.summary = $summary
                    """,
                    {"title": t['title'], "summary": t.get('summary', '')}
                )
                
                # 관계: 누가 이 주제를 꺼냈나?
                if 'proposer' in t:
                    # Person과 Topic이 확실히 있을 때만 연결
                    self.conn.execute(
                        "MATCH (p:Person {name: $name}), (t:Topic {title: $title}) "
                        "MERGE (p)-[:PROPOSED]->(t)",
                        {"name": t['proposer'], "title": t['title']}
                    )

            # 3. Task 노드 (내용으로 찾고, 마감일 업데이트)
            for task in analysis_result.get("tasks", []):
                desc_text = task.get('description', task.get('desc', 'No Description'))
                
                self.conn.execute(
                    """
                    MERGE (t:Task {description: $task_desc})
                    ON CREATE SET t.deadline = $due, t.status = 'To Do'
                    ON MATCH SET t.deadline = $due
                    """,
                    # 파라미터 키를 'desc' -> 'task_desc'로 변경
                    {"task_desc": desc_text, "due": task.get('deadline', 'TBD')}
                )
                if 'assignee' in task:
                    self.conn.execute(
                        "MATCH (p:Person {name: $name}), (t:Task {description: $desc}) "
                        "MERGE (p)-[:ASSIGNED_TO]->(t)",
                        {"name": task['assignee'], "desc": desc_text}
                    )

            # 4. Decision 노드
            for d in analysis_result.get("decisions", []):
                desc_text = d.get('description', d.get('desc', 'No Description'))
                
                self.conn.execute(
                    "MERGE (d:Decision {description: $desc})",
                    {"desc": desc_text}
                )

            print(f"🎉 데이터 적재 완료! (Topics: {len(analysis_result.get('topics', []))}개)")
            
        except Exception as e:
            print(f"❌ 데이터 적재 중 오류 발생: {e}")

# 테스트용 코드
if __name__ == "__main__":
    db = KuzuManager()
    dummy_data = {
        "people": [{"name": "김철수", "role": "팀장"}],
        "topics": [{"title": "DB 설계", "summary": "KuzuDB 스키마 논의", "proposer": "김철수"}],
        "tasks": [{"desc": "스키마 작성", "assignee": "김철수"}]
    }
    db.ingest_data(dummy_data)