"""Central configuration for all SpeakNode modules."""
import os
from dataclasses import dataclass, field


def _default_db_base_dir() -> str:
    project_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
    return os.path.join(project_root, "database", "chats")


def _default_api_max_workers() -> int:
    cpu_count = os.cpu_count() or 2
    return max(2, min(8, cpu_count))


def _default_api_agent_workers() -> int:
    return _default_api_max_workers()


@dataclass
class SpeakNodeConfig:
    # STT
    whisper_model: str = "large-v3"
    whisper_language: str = "ko"
    whisper_beam_size: int = 5

    # Speaker diarization
    enable_diarization: bool = False
    hf_token: str = ""

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384
    embedding_batch_size: int = 64

    # LLM
    llm_model: str = "qwen2.5:14b"
    llm_temperature: float = 0.0

    # Agent
    agent_model: str = "qwen2.5:14b"
    agent_max_iterations: int = 10

    # API Runtime
    api_max_workers: int = field(default_factory=_default_api_max_workers)
    api_analyze_workers: int = 1
    api_agent_workers: int = field(default_factory=_default_api_agent_workers)
    api_graph_import_max_bytes: int = 25 * 1024 * 1024
    api_graph_import_max_elements: int = 200_000

    # Database
    db_base_dir: str = field(default_factory=_default_db_base_dir)
    default_chat_id: str = "default"

    def get_chat_db_path(self, chat_id: str | None = None) -> str:
        cid = chat_id or self.default_chat_id
        return os.path.join(self.db_base_dir, f"{cid}.kuzu")


# Chat session helpers — co-located to avoid circular imports.
import re as _re


def sanitize_chat_id(raw: str) -> str:
    safe = _re.sub(r"[^0-9A-Za-z_-]+", "_", (raw or "").strip()).strip("_")
    return safe or "default"


def get_chat_db_path(chat_id: str, config: SpeakNodeConfig | None = None) -> str:
    cfg = config or SpeakNodeConfig()
    return cfg.get_chat_db_path(sanitize_chat_id(chat_id))


def list_chat_ids(config: SpeakNodeConfig | None = None) -> list[str]:
    cfg = config or SpeakNodeConfig()
    chat_ids = []
    if os.path.exists(cfg.db_base_dir):
        for name in os.listdir(cfg.db_base_dir):
            if name.endswith(".kuzu"):
                chat_ids.append(name[:-5])
    return sorted(chat_ids)
