import kuzu
import os

def check_database():
    print("🚀 [Debug] DB 검증 스크립트 시작!")
    
    # 1. 현재 경로 확인
    current_dir = os.getcwd()
    print(f"📍 현재 작업 경로: {current_dir}")
    
    # 2. DB 경로 찾기
    db_path = "./database/speaknode.kuzu"
    
    if not os.path.exists(os.path.dirname(db_path)):
        print(f"❌ DB 폴더를 찾을 수 없습니다: {db_path}")
        return

    print(f"🔎 DB 찾는 중: {db_path}")

    try:
        # 3. DB 연결
        db = kuzu.Database(db_path)
        conn = kuzu.Connection(db)
        print("✅ DB 연결 성공!")
        
        # 4. 전체 테이블 목록 확인
        print("\n--- [1. 테이블 목록 조회] ---")
        tables_result = conn.execute("CALL show_tables() RETURN *")
        
        # [수정] hasNext() -> has_next() / getNext() -> get_next()
        while tables_result.has_next():
            print(f"   📄 {tables_result.get_next()}")
            
        # 5. 각 테이블별 데이터 개수 세기
        print("\n--- [2. 데이터 개수 카운트] ---")
        target_tables = ["Person", "Topic", "Task", "Decision", "Utterance"]
        
        for table in target_tables:
            try:
                count_result = conn.execute(f"MATCH (n:{table}) RETURN count(n)")
                if count_result.has_next():
                    count = count_result.get_next()[0]
                    print(f"   📊 {table}: {count}개")
            except Exception as e:
                # 테이블이 없으면 그냥 넘어감
                pass

        # 6. 실제 데이터(Topic) 내용 까보기
        print("\n--- [3. Topic 데이터 내용] ---")
        topic_result = conn.execute("MATCH (t:Topic) RETURN t.title, t.summary")
        
        if topic_result.has_next():
            while topic_result.has_next():
                row = topic_result.get_next()
                print(f"   📌 제목: {row[0]}")
                # 요약이 있을 경우 출력
                summary = row[1] if row[1] else "(내용 없음)"
                print(f"   📝 요약: {summary}")
        else:
            print("   (저장된 Topic 데이터가 없습니다.)")
            
    except Exception as e:
        print(f"\n❌ [Error] : {e}")

if __name__ == "__main__":
    check_database()