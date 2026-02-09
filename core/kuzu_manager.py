import kuzu
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class KuzuManager:
    def __init__(self):
        # .env에서 경로 읽기 (기본값 설정 포함)
        db_path = os.getenv("DB_PATH", "data/speachnode_db")
        
        self.abs_db_path = os.path.abspath(db_path)
        db_dir = os.path.dirname(self.abs_db_path)
        
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)
        
        self.db = kuzu.Database(self.abs_db_path)
        self.conn = kuzu.Connection(self.db)
        self._initialize_schema()

    def _initialize_schema(self):
        try:
            # Nodes
            self.conn.execute("CREATE NODE TABLE Meeting(id SERIAL, title STRING, date DATE, PRIMARY KEY (id))")
            self.conn.execute("CREATE NODE TABLE Utterance(id SERIAL, content STRING, timestamp STRING, PRIMARY KEY (id))")
            self.conn.execute("CREATE NODE TABLE Speaker(name STRING, PRIMARY KEY (name))")

            # Relationships
            self.conn.execute("CREATE REL TABLE CONTAINS(FROM Meeting TO Utterance)")
            self.conn.execute("CREATE REL TABLE SPOKE(FROM Speaker TO Utterance)")
            
            print(f"✅ KuzuDB 스키마 연결 완료 (경로: {self.abs_db_path})")
        except Exception as e:
            if "already exists" in str(e):
                print("ℹ️ 기존 스키마를 로드했습니다.")
            else:
                print(f"❌ DB 초기화 오류: {e}")

if __name__ == "__main__":
    manager = KuzuManager()