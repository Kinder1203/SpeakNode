from __future__ import annotations

import asyncio
import logging
import os
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core.config import SpeakNodeConfig, get_chat_db_path, list_chat_ids, sanitize_chat_id
from core.db.kuzu_manager import KuzuManager, decode_scoped_value
from core.pipeline import SpeakNodeEngine
from core.utils import ALLOWED_TASK_STATUSES

# Runtime Configuration
logger = logging.getLogger("speaknode.api")
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a"}
MAX_AUDIO_SIZE_BYTES = 512 * 1024 * 1024  # 512 MB
TEMP_UPLOAD_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "../../temp_uploads",
)

engine: SpeakNodeEngine | None = None
config = SpeakNodeConfig()
analyze_executor = ThreadPoolExecutor(max_workers=max(1, int(config.api_analyze_workers)))
agent_executor = ThreadPoolExecutor(max_workers=max(1, int(config.api_agent_workers)))

os.makedirs(config.db_base_dir, exist_ok=True)
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)

_chat_locks: dict[str, asyncio.Lock] = {}
_chat_locks_guard = asyncio.Lock()


# Request Models
class CreateChatRequest(BaseModel):
    chat_id: str = Field(min_length=1)


class AgentQueryRequest(BaseModel):
    question: str = Field(min_length=1)
    chat_id: str = "default"


class GraphImportRequest(BaseModel):
    chat_id: str = "default"
    graph_dump: dict[str, Any]


class NodeUpdateRequest(BaseModel):
    chat_id: str = "default"
    node_type: str = Field(description="Topic | Task | Person | Meeting")
    node_id: str = Field(min_length=1, description="Primary key value")
    fields: dict[str, Any] = Field(default_factory=dict)


NODE_UPDATE_RULES: dict[str, dict[str, Any]] = {
    "Topic": {"pk": "title", "fields": {"summary"}},
    "Task": {"pk": "description", "fields": {"deadline", "status"}},
    "Person": {"pk": "name", "fields": {"role"}},
    "Meeting": {"pk": "id", "fields": {"title", "date", "source_file"}},
    "Decision": {"pk": "description", "fields": set()},
}


# Helper Functions
def _normalize_chat_id(raw: str) -> str:
    return sanitize_chat_id(raw or "default")


def _chat_db_path(chat_id: str) -> str:
    return get_chat_db_path(_normalize_chat_id(chat_id), config)


def _ensure_engine() -> SpeakNodeEngine:
    if engine is None:
        raise HTTPException(status_code=503, detail="Server not ready")
    return engine


async def _get_chat_lock(chat_id: str) -> asyncio.Lock:
    async with _chat_locks_guard:
        lock = _chat_locks.get(chat_id)
        if lock is None:
            lock = asyncio.Lock()
            _chat_locks[chat_id] = lock
        return lock


def _uploaded_file_size(upload: UploadFile) -> int:
    try:
        upload.file.seek(0, os.SEEK_END)
        size = upload.file.tell()
        upload.file.seek(0)
        return int(size)
    except Exception:
        return -1


def _validate_audio_upload(upload: UploadFile) -> str:
    filename = upload.filename or "audio.bin"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension: {ext or '(none)'}",
        )

    size = _uploaded_file_size(upload)
    if size < 0:
        raise HTTPException(
            status_code=400,
            detail="Unable to determine file size",
        )
    if size > MAX_AUDIO_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({size} bytes). Max: {MAX_AUDIO_SIZE_BYTES} bytes",
        )
    return ext


def _temp_upload_path(ext: str) -> str:
    return os.path.join(TEMP_UPLOAD_DIR, f"{uuid.uuid4()}{ext}")


def _init_chat_db(chat_id: str) -> str:
    db_path = _chat_db_path(chat_id)
    with KuzuManager(db_path=db_path, config=config):
        return db_path


def _graph_dump_element_count(graph_dump: dict[str, Any]) -> int:
    total = 0
    nodes = graph_dump.get("nodes", {}) if isinstance(graph_dump, dict) else {}
    edges = graph_dump.get("edges", {}) if isinstance(graph_dump, dict) else {}
    for bucket in (nodes, edges):
        if not isinstance(bucket, dict):
            continue
        for value in bucket.values():
            if isinstance(value, list):
                total += len(value)
    return total


# Lifespan / App
@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    logger.info("Starting SpeakNode API server")
    try:
        engine = SpeakNodeEngine(config=config)
    except Exception as exc:
        logger.exception("Engine initialization failed")
        raise RuntimeError("Failed to initialize SpeakNode engine") from exc

    yield

    logger.info("Shutting down SpeakNode API server")
    analyze_executor.shutdown(wait=True)
    agent_executor.shutdown(wait=True)


app = FastAPI(
    title="SpeakNode API",
    version="5.2.0",
    lifespan=lifespan,
    description="Local meeting analysis API (STT + Graph DB + Agent)",
)

# CORS 
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("SPEAKNODE_CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_size_guard(request: Request, call_next):
    if request.url.path == "/graph/import":
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
            except ValueError:
                size = 0
            if size > config.api_graph_import_max_bytes:
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": (
                            f"Request body too large ({size} bytes). "
                            f"Max: {config.api_graph_import_max_bytes} bytes"
                        )
                    },
                )
    return await call_next(request)


# Core API
@app.post("/analyze")
async def analyze_audio(
    file: UploadFile = File(...),
    chat_id: str = Form("default"),
    meeting_title: str = Form(""),
):
    runtime = _ensure_engine()
    safe_chat_id = _normalize_chat_id(chat_id)
    chat_db_path = _chat_db_path(safe_chat_id)
    file_ext = _validate_audio_upload(file)
    lock = await _get_chat_lock(safe_chat_id)

    async with lock:
        temp_path = _temp_upload_path(file_ext)
        try:
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                analyze_executor,
                runtime.process,
                temp_path,
                chat_db_path,
                (meeting_title or "").strip(),
            )
            if result is None:
                raise HTTPException(status_code=400, detail="No speech detected")

            return {"status": "success", "chat_id": safe_chat_id, "data": result}
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Analyze request failed")
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    logger.warning("Failed to remove temp file: %s", temp_path)


@app.get("/health")
def health_check():
    return {
        "status": "online",
        "engine_ready": engine is not None,
        "chat_count": len(list_chat_ids(config)),
        "version": app.version,
    }


@app.get("/chats")
def get_chats():
    return {"status": "success", "chats": list_chat_ids(config)}


@app.post("/chats")
async def create_chat(payload: CreateChatRequest):
    safe_chat_id = _normalize_chat_id(payload.chat_id)
    lock = await _get_chat_lock(safe_chat_id)
    async with lock:
        db_path = _init_chat_db(safe_chat_id)
    return {"status": "success", "chat_id": safe_chat_id, "db_path": db_path}


@app.delete("/chats/{chat_id}")
async def reset_chat(chat_id: str):
    safe_chat_id = _normalize_chat_id(chat_id)
    db_path = _chat_db_path(safe_chat_id)
    lock = await _get_chat_lock(safe_chat_id)

    async with lock:
        if not os.path.exists(db_path):
            return {"status": "success", "chat_id": safe_chat_id, "message": "already empty"}
        try:
            if os.path.isfile(db_path):
                os.remove(db_path)
            else:
                shutil.rmtree(db_path)
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"failed to reset chat db: {exc}",
            ) from exc

    # Remove stale lock after DB deletion
    async with _chat_locks_guard:
        _chat_locks.pop(safe_chat_id, None)

    return {"status": "success", "chat_id": safe_chat_id, "message": "reset complete"}


# Agent API
@app.post("/agent/query")
async def agent_query(payload: AgentQueryRequest):
    runtime = _ensure_engine()
    safe_chat_id = _normalize_chat_id(payload.chat_id)
    chat_db_path = _chat_db_path(safe_chat_id)

    if not os.path.exists(chat_db_path):
        raise HTTPException(
            status_code=404,
            detail=f"Chat '{safe_chat_id}' DB not found. Analyze audio first.",
        )

    lock = await _get_chat_lock(safe_chat_id)
    async with lock:
        try:
            loop = asyncio.get_running_loop()
            agent = runtime.create_agent(db_path=chat_db_path)
            response = await loop.run_in_executor(agent_executor, agent.query, payload.question)
            return {"status": "success", "chat_id": safe_chat_id, "answer": response}
        except Exception as exc:
            logger.exception("Agent query failed")
            raise HTTPException(status_code=500, detail=str(exc)) from exc


# API (Server Hardening / Production Support)
@app.get("/meetings")
async def list_meetings(
    chat_id: str = Query("default"),
    limit: int = Query(50, ge=1, le=200),
):
    safe_chat_id = _normalize_chat_id(chat_id)
    chat_db_path = _chat_db_path(safe_chat_id)
    if not os.path.exists(chat_db_path):
        return {"status": "success", "chat_id": safe_chat_id, "meetings": []}

    lock = await _get_chat_lock(safe_chat_id)
    async with lock:
        with KuzuManager(db_path=chat_db_path, config=config) as db:
            meetings = db.get_all_meetings(limit=limit)
    return {"status": "success", "chat_id": safe_chat_id, "meetings": meetings}


@app.get("/meetings/{meeting_id}")
async def get_meeting_detail(
    meeting_id: str,
    chat_id: str = Query("default"),
):
    safe_chat_id = _normalize_chat_id(chat_id)
    chat_db_path = _chat_db_path(safe_chat_id)
    if not os.path.exists(chat_db_path):
        raise HTTPException(status_code=404, detail=f"Chat '{safe_chat_id}' DB not found.")

    lock = await _get_chat_lock(safe_chat_id)
    async with lock:
        with KuzuManager(db_path=chat_db_path, config=config) as db:
            summary = db.get_meeting_summary(meeting_id)
    if not summary:
        raise HTTPException(status_code=404, detail=f"Meeting '{meeting_id}' not found.")
    return {"status": "success", "chat_id": safe_chat_id, "meeting": summary}


@app.get("/graph/export")
async def export_graph(
    chat_id: str = Query("default"),
    include_embeddings: bool = Query(False, description="Include utterance embeddings in graph dump"),
):
    safe_chat_id = _normalize_chat_id(chat_id)
    chat_db_path = _chat_db_path(safe_chat_id)
    if not os.path.exists(chat_db_path):
        return {"status": "success", "chat_id": safe_chat_id, "graph_dump": {}}

    lock = await _get_chat_lock(safe_chat_id)
    async with lock:
        with KuzuManager(db_path=chat_db_path, config=config) as db:
            graph_dump = db.export_graph_dump(include_embeddings=include_embeddings)
    return {"status": "success", "chat_id": safe_chat_id, "graph_dump": graph_dump}


@app.post("/graph/import")
async def import_graph(payload: GraphImportRequest):
    safe_chat_id = _normalize_chat_id(payload.chat_id)
    lock = await _get_chat_lock(safe_chat_id)
    chat_db_path = _chat_db_path(safe_chat_id)
    dump = payload.graph_dump if isinstance(payload.graph_dump, dict) else {}

    payload_size = len(payload.model_dump_json().encode("utf-8"))
    if payload_size > config.api_graph_import_max_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"graph_dump payload too large ({payload_size} bytes). "
                f"Max: {config.api_graph_import_max_bytes} bytes"
            ),
        )

    element_count = _graph_dump_element_count(dump)
    if element_count > config.api_graph_import_max_elements:
        raise HTTPException(
            status_code=413,
            detail=(
                f"graph_dump element count too large ({element_count}). "
                f"Max: {config.api_graph_import_max_elements}"
            ),
        )

    async with lock:
        with KuzuManager(db_path=chat_db_path, config=config) as db:
            db.restore_graph_dump(dump)
    return {"status": "success", "chat_id": safe_chat_id, "message": "graph imported"}


@app.patch("/nodes/update")
async def update_node(payload: NodeUpdateRequest):
    safe_chat_id = _normalize_chat_id(payload.chat_id)
    chat_db_path = _chat_db_path(safe_chat_id)
    if not os.path.exists(chat_db_path):
        raise HTTPException(status_code=404, detail=f"Chat '{safe_chat_id}' DB not found.")

    rule = NODE_UPDATE_RULES.get(payload.node_type)
    if rule is None:
        raise HTTPException(status_code=400, detail=f"Unsupported node_type: {payload.node_type}")
    if not payload.fields:
        raise HTTPException(status_code=400, detail="fields must not be empty")

    invalid = [name for name in payload.fields if name not in rule["fields"]]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unsupported fields: {invalid}")
    if payload.node_type == "Task" and "status" in payload.fields:
        status = str(payload.fields["status"]).strip()
        if status not in ALLOWED_TASK_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported task status: {status}. Allowed: {sorted(ALLOWED_TASK_STATUSES)}",
            )

    params: dict[str, Any] = {"node_id": payload.node_id}
    set_clauses: list[str] = []
    for field, value in payload.fields.items():
        param_name = f"val_{field}"
        set_clauses.append(f"n.{field} = ${param_name}")
        params[param_name] = value

    query = (
        f"MATCH (n:{payload.node_type} {{{rule['pk']}: $node_id}}) "
        f"SET {', '.join(set_clauses)} "
        "RETURN count(n)"
    )

    lock = await _get_chat_lock(safe_chat_id)
    async with lock:
        with KuzuManager(db_path=chat_db_path, config=config) as db:
            rows = db.execute_cypher(query, params)
            updated = rows[0][0] if rows else 0

            if updated == 0 and payload.node_type in {"Topic", "Task"}:
                key_name = rule["pk"]
                candidates = db.execute_cypher(f"MATCH (n:{payload.node_type}) RETURN n.{key_name} LIMIT 5000")
                scoped_matches = [
                    row[0]
                    for row in candidates
                    if row[0] == payload.node_id or decode_scoped_value(row[0]) == payload.node_id
                ]
                if len(scoped_matches) > 1:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"Ambiguous node_id '{payload.node_id}'. "
                            "Multiple scoped nodes found; use raw scoped id."
                        ),
                    )
                if len(scoped_matches) == 1:
                    params["node_id"] = scoped_matches[0]
                    rows = db.execute_cypher(query, params)
                    updated = rows[0][0] if rows else 0
    if updated == 0:
        raise HTTPException(status_code=404, detail="Target node not found")

    return {"status": "success", "chat_id": safe_chat_id, "updated": int(updated)}
