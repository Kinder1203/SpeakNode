"""
SpeakNode Embedding 모델 캐시
==============================
프로세스 전체에서 동일한 embedding 모델을 단 한 번만 로드합니다.
SpeakNodeEngine과 HybridRAG가 동일 인스턴스를 공유하여
RAM/VRAM 중복 사용을 방지합니다.

Thread-safe: double-checked locking 패턴 적용.
"""

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
    """
    모델명 기준으로 SentenceTransformer 인스턴스를 반환합니다.
    최초 호출 시 모델을 로드하고, 이후에는 캐시된 인스턴스를 반환합니다.
    """
    if model_name not in _cache:
        with _lock:
            if model_name not in _cache:
                from sentence_transformers import SentenceTransformer

                logger.info("⏳ Embedding 모델 로딩: '%s'", model_name)
                _cache[model_name] = SentenceTransformer(model_name)
                logger.info("✅ Embedding 모델 로드 완료: '%s'", model_name)
    return _cache[model_name]
