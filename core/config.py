# Central configuration for all SpeakNode modules.
import os
import re as _re
from dataclasses import dataclass, field


def _default_db_base_dir() -> str:
    project_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
    return os.path.join(project_root, "database", "meetings")


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

    # Database  — 1 meeting = 1 independent KuzuDB directory
    db_base_dir: str = field(default_factory=_default_db_base_dir)

    def get_meeting_db_path(self, meeting_id: str | None = None) -> str:
        mid = meeting_id or "default"
        return os.path.join(self.db_base_dir, mid)


# Meeting session helpers — co-located to avoid circular imports.


def sanitize_meeting_id(raw: str) -> str:
    safe = _re.sub(r"[^0-9A-Za-z_-]+", "_", (raw or "").strip()).strip("_")
    return safe or "default"


def get_meeting_db_path(meeting_id: str, config: SpeakNodeConfig | None = None) -> str:
    cfg = config or SpeakNodeConfig()
    return cfg.get_meeting_db_path(sanitize_meeting_id(meeting_id))


def list_meeting_ids(config: SpeakNodeConfig | None = None) -> list[str]:
    """Return meeting IDs (directory names) sorted most-recent first."""
    cfg = config or SpeakNodeConfig()
    meeting_ids: list[str] = []
    if os.path.exists(cfg.db_base_dir):
        for name in os.listdir(cfg.db_base_dir):
            full_path = os.path.join(cfg.db_base_dir, name)
            if os.path.isdir(full_path):
                meeting_ids.append(name)
    # IDs start with m_YYYYMMDD — reverse-alpha gives most-recent first.
    return sorted(meeting_ids, reverse=True)
