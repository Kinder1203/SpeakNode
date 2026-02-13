from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from pydantic import BaseModel
from contextlib import asynccontextmanager
import shutil
import os
import sys
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor

from core.pipeline import SpeakNodeEngine
from core.db.kuzu_manager import KuzuManager
from core.config import SpeakNodeConfig, sanitize_chat_id, get_chat_db_path, list_chat_ids

# Global State
engine = None
config = SpeakNodeConfig()
# Kuzu 단일 파일 DB 잠금 충돌을 줄이기 위해 동시 분석 워커를 1로 제한
executor = ThreadPoolExecutor(max_workers=1)
TEMP_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../temp_uploads")
os.makedirs(config.db_base_dir, exist_ok=True)
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)


def init_chat_db(chat_id: str) -> str:
    db_path = get_chat_db_path(chat_id, config)
    mgr = KuzuManager(db_path=db_path)
    mgr.close()
    return db_path


class CreateChatRequest(BaseModel):
    chat_id: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    print("🚀 [Server] 서버 시작: SpeakNode Engine 로딩 중...")
    try:
        engine = SpeakNodeEngine()
        print("✅ [Server] 엔진 로딩 완료.")
    except Exception as e:
        print(f"🔥 [Critical] 엔진 로딩 실패: {e}")
        sys.exit(1)
    
    yield
    
    print("👋 [Server] 서버 종료")
    executor.shutdown()

app = FastAPI(title="SpeakNode API", lifespan=lifespan)

@app.post("/analyze")
async def analyze_audio(file: UploadFile = File(...), chat_id: str = Form("default")):
    if not engine:
        raise HTTPException(status_code=503, detail="Server not ready")

    safe_chat_id = sanitize_chat_id(chat_id)
    chat_db_path = get_chat_db_path(safe_chat_id, config)

    # 1. UUID 파일명 생성
    original_name = file.filename or "audio.bin"
    file_ext = os.path.splitext(original_name)[1]
    safe_filename = f"{uuid.uuid4()}{file_ext}"
    temp_path = os.path.join(TEMP_UPLOAD_DIR, safe_filename)
    
    if not os.path.exists(os.path.dirname(temp_path)):
        os.makedirs(os.path.dirname(temp_path))

    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(executor, engine.process, temp_path, chat_db_path)
        
        if result is None:
             raise HTTPException(status_code=400, detail="No speech detected")

        return {"status": "success", "chat_id": safe_chat_id, "data": result}

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ 내부 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


@app.get("/health")
def health_check():
    return {
        "status": "online",
        "engine_ready": engine is not None,
        "chat_count": len(list_chat_ids(config)),
    }


@app.get("/chats")
def get_chats():
    return {"status": "success", "chats": list_chat_ids(config)}


@app.post("/chats")
def create_chat(payload: CreateChatRequest):
    safe_chat_id = sanitize_chat_id(payload.chat_id)
    db_path = init_chat_db(safe_chat_id)
    return {
        "status": "success",
        "chat_id": safe_chat_id,
        "db_path": db_path,
    }


@app.delete("/chats/{chat_id}")
def reset_chat(chat_id: str):
    safe_chat_id = sanitize_chat_id(chat_id)
    db_path = get_chat_db_path(safe_chat_id, config)
    if not os.path.exists(db_path):
        return {"status": "success", "chat_id": safe_chat_id, "message": "already empty"}

    try:
        if os.path.isfile(db_path):
            os.remove(db_path)
        else:
            shutil.rmtree(db_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"failed to reset chat db: {e}")

    return {"status": "success", "chat_id": safe_chat_id, "message": "reset complete"}


# ================================================================
# 🤖 Agent API (Phase 4)
# ================================================================

class AgentQueryRequest(BaseModel):
    question: str
    chat_id: str = "default"


@app.post("/agent/query")
async def agent_query(payload: AgentQueryRequest):
    """Agent에게 자연어 질의를 보내고 응답을 받습니다."""
    if not engine:
        raise HTTPException(status_code=503, detail="Server not ready")

    safe_chat_id = sanitize_chat_id(payload.chat_id)
    chat_db_path = get_chat_db_path(safe_chat_id, config)

    if not os.path.exists(chat_db_path):
        raise HTTPException(
            status_code=404,
            detail=f"Chat '{safe_chat_id}' DB가 존재하지 않습니다. 먼저 오디오를 분석해주세요.",
        )

    try:
        loop = asyncio.get_running_loop()
        agent = engine.create_agent(db_path=chat_db_path)
        response = await loop.run_in_executor(
            executor, agent.query, payload.question
        )
        return {"status": "success", "chat_id": safe_chat_id, "answer": response}
    except Exception as e:
        print(f"❌ Agent 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))
