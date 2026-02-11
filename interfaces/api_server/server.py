from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from contextlib import asynccontextmanager
import shutil
import os
import sys
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor

# 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../"))
sys.path.append(project_root)

from core.pipeline import SpeakNodeEngine

# Global State
engine = None
executor = ThreadPoolExecutor(max_workers=3)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    print("🚀 [Server] 서버 시작: SpeakNode Engine 로딩 중...")
    try:
        engine = SpeakNodeEngine()
        print("✅ [Server] 엔진 로딩 완료.")
    except Exception as e:
        print(f"🔥 [Critical] 엔진 로딩 실패: {e}")
        # [Fix] 초기화 실패 시 서버를 종료시켜야 함 (계속 실행되면 503 좀비 서버 됨)
        sys.exit(1)
    
    yield
    
    print("👋 [Server] 서버 종료")
    executor.shutdown()

app = FastAPI(title="SpeakNode API", lifespan=lifespan)

@app.post("/analyze")
async def analyze_audio(file: UploadFile = File(...)):
    if not engine:
        raise HTTPException(status_code=503, detail="Server not ready")

    # 1. UUID 파일명 생성
    file_ext = os.path.splitext(file.filename)[1]
    safe_filename = f"{uuid.uuid4()}{file_ext}"
    temp_path = os.path.join(project_root, "temp_uploads", safe_filename)
    
    if not os.path.exists(os.path.dirname(temp_path)):
        os.makedirs(os.path.dirname(temp_path))

    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(executor, engine.process, temp_path)
        
        if result is None:
             raise HTTPException(status_code=400, detail="No speech detected")

        return {"status": "success", "data": result}

    # [Fix] HTTPException은 그대로 통과시켜야 클라이언트가 400/404 등을 구분 가능
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ 내부 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except: pass