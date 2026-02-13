"""
SpeakNode 중앙 설정 (Central Configuration)
============================================
모든 모듈이 참조하는 단일 설정 소스.
모델명, 차원, 경로 등을 한 곳에서 관리하여
값 변경 시 여러 파일을 동시에 수정할 필요가 없도록 합니다.
"""
import os
from dataclasses import dataclass, field


def _default_db_base_dir() -> str:
    """프로젝트 루트 기준 기본 DB 디렉토리 계산"""
    project_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
    return os.path.join(project_root, "database", "chats")


def _default_api_max_workers() -> int:
    cpu_count = os.cpu_count() or 2
    return max(2, min(8, cpu_count))


@dataclass
class SpeakNodeConfig:
    """SpeakNode 전체 설정을 담는 데이터 클래스"""

    # --- STT (귀) ---
    whisper_model: str = "large-v3"
    whisper_language: str = "ko"
    whisper_beam_size: int = 5

    # --- Speaker Diarization (화자 분리) ---
    enable_diarization: bool = False
    hf_token: str = ""  # pyannote.audio HuggingFace 토큰

    # --- Embedding (이해) ---
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384
    embedding_batch_size: int = 64  # OOM 방지를 위한 배치 크기

    # --- LLM (지능) ---
    llm_model: str = "qwen2.5:14b"
    llm_temperature: float = 0.0

    # --- Agent (Phase 4) ---
    agent_model: str = "qwen2.5:14b"  # Agent LLM (기본: llm_model과 동일)
    agent_max_iterations: int = 10    # Agent 최대 반복 횟수

    # --- API Runtime ---
    api_max_workers: int = field(default_factory=_default_api_max_workers)

    # --- Database (기억) ---
    db_base_dir: str = field(default_factory=_default_db_base_dir)
    default_chat_id: str = "default"

    # ---- 파생 속성 ----

    def get_chat_db_path(self, chat_id: str | None = None) -> str:
        """chat_id에 해당하는 DB 파일 경로 반환"""
        cid = chat_id or self.default_chat_id
        return os.path.join(self.db_base_dir, f"{cid}.kuzu")


# ================================================================
# Chat Session 유틸리티 (app.py / server.py 공유)
# ================================================================

import re as _re


def sanitize_chat_id(raw: str) -> str:
    """채팅 ID에서 안전하지 않은 문자 제거"""
    safe = _re.sub(r"[^0-9A-Za-z_-]+", "_", (raw or "").strip()).strip("_")
    return safe or "default"


def get_chat_db_path(chat_id: str, config: SpeakNodeConfig | None = None) -> str:
    """chat_id에 해당하는 DB 경로 반환 (standalone 버전)"""
    cfg = config or SpeakNodeConfig()
    return cfg.get_chat_db_path(sanitize_chat_id(chat_id))


def list_chat_ids(config: SpeakNodeConfig | None = None) -> list[str]:
    """DB 디렉토리에서 존재하는 채팅 ID 목록 반환"""
    cfg = config or SpeakNodeConfig()
    chat_ids = []
    if os.path.exists(cfg.db_base_dir):
        for name in os.listdir(cfg.db_base_dir):
            if name.endswith(".kuzu"):
                chat_ids.append(name[:-5])
    return sorted(chat_ids)
