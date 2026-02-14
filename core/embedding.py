"""Process-wide singleton cache for SentenceTransformer models."""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_cache: dict[str, SentenceTransformer] = {}
_lock = threading.Lock()


def get_embedder(model_name: str) -> SentenceTransformer:
    """Return a cached SentenceTransformer, loading on first call."""
    if model_name not in _cache:
        with _lock:
            if model_name not in _cache:
                from sentence_transformers import SentenceTransformer

                logger.info("Loading embedding model: '%s'", model_name)
                _cache[model_name] = SentenceTransformer(model_name)
                logger.info("Embedding model ready: '%s'", model_name)
    return _cache[model_name]
