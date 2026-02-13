"""
SpeakNode Pipeline — AI 엔진
=============================
Lazy Loading: 각 모듈은 처음 사용될 때만 메모리에 로드됩니다.
Agent만 사용하는 경우 Whisper 모델(수 GB)을 로드하지 않습니다.
"""

import datetime
import logging
import os
import threading

from core.config import SpeakNodeConfig
from core.db.kuzu_manager import KuzuManager
from core.embedding import get_embedder

logger = logging.getLogger(__name__)


class SpeakNodeEngine:
    """
    SpeakNode AI 엔진.
    @property 기반 지연 로딩으로 사용하지 않는 모듈은 메모리에 올리지 않습니다.
    - STT (귀) → Embedding (이해) → LLM (지능) → DB (기억)
    """

    def __init__(self, config: SpeakNodeConfig = None):
        self.config = config or SpeakNodeConfig()
        # Private slots — None 이면 아직 로드 안 됨
        self._transcriber = None
        self._extractor = None
        self._transcriber_init_lock = threading.Lock()
        self._extractor_init_lock = threading.Lock()
        self._transcriber_run_lock = threading.Lock()
        self._embedder_run_lock = threading.Lock()
        self._extractor_run_lock = threading.Lock()
        logger.info("🚀 [System] 엔진 준비 (Lazy Loading — 모듈은 사용 시 로드됩니다)")

    # ================================================================
    # 🔋 Lazy Properties — 최초 접근 시 1회만 로딩
    # ================================================================

    @property
    def transcriber(self):
        if self._transcriber is None:
            with self._transcriber_init_lock:
                if self._transcriber is None:
                    from core.stt.transcriber import Transcriber
                    logger.info("   ⏳ Loading Whisper (Ear)...")
                    self._transcriber = Transcriber(config=self.config)
        return self._transcriber

    @property
    def embedder(self):
        """Embedding 모델 — 프로세스 전역 싱글턴 캐시를 통해 반환."""
        return get_embedder(self.config.embedding_model)

    @property
    def extractor(self):
        if self._extractor is None:
            with self._extractor_init_lock:
                if self._extractor is None:
                    from core.llm.extractor import Extractor
                    logger.info("   ⏳ Loading LLM (Brain)...")
                    self._extractor = Extractor(config=self.config)
        return self._extractor

    # ================================================================
    # 📌 개별 단계 — Agent가 독립적으로 호출 가능
    # ================================================================

    def transcribe(self, audio_path: str) -> list[dict] | None:
        """Step 1: STT만 수행. 오디오 → 세그먼트 리스트 반환."""
        if not os.path.exists(audio_path):
            logger.error("⚠️ [Error] File not found: %s", audio_path)
            return None

        logger.info("🎧 [Pipeline] STT 시작: %s", os.path.basename(audio_path))
        with self._transcriber_run_lock:
            result = self.transcriber.transcribe(audio_path)

        if not result:
            logger.error("❌ [Pipeline] STT 실패 또는 결과 없음.")
            return None
        return result

    def embed(self, segments: list[dict]) -> list[list[float]]:
        """Step 2: 세그먼트 텍스트를 벡터로 변환. OOM 방지 배치 인코딩."""
        texts = [seg["text"] for seg in segments]
        batch_size = self.config.embedding_batch_size
        all_embeddings = []

        with self._embedder_run_lock:
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                batch_vectors = self.embedder.encode(batch).tolist()
                all_embeddings.extend(batch_vectors)

        return all_embeddings

    def extract(self, transcript_text: str):
        """Step 3: 텍스트에서 Topic/Task/Decision 추출."""
        with self._extractor_run_lock:
            return self.extractor.extract(transcript_text)

    # ================================================================
    # 🔄 통합 파이프라인 — 전체 흐름 실행
    # ================================================================

    def process(self, audio_path: str, db_path: str | None = None, meeting_title: str | None = None):
        """전체 파이프라인: STT → Embedding → LLM → DB 적재"""
        logger.info("▶️ [Pipeline] 분석 시작: %s", os.path.basename(audio_path))

        # --- Step 1: STT ---
        segments = self.transcribe(audio_path)
        if not segments:
            return None

        transcript_text = " ".join([seg.get("text", "") for seg in segments]).strip()
        if not transcript_text or transcript_text.lower() in ("none", "[]"):
            logger.warning("⚠️ [Warning] 유효한 텍스트가 없습니다.")
            return None

        # --- Step 2: Embedding + DB 적재 ---
        logger.info("   Step 2: 문맥 벡터화 및 대화 흐름 저장...")
        target_db_path = db_path if db_path else self.config.get_chat_db_path()

        with KuzuManager(db_path=target_db_path, config=self.config) as db:
            now = datetime.datetime.now()
            meeting_id = f"m_{now.strftime('%Y%m%d_%H%M%S_%f')}"
            normalized_title = (meeting_title or "").strip()
            if not normalized_title:
                source_name = os.path.splitext(os.path.basename(audio_path))[0].strip()
                normalized_title = source_name or f"회의_{now.strftime('%Y-%m-%d_%H:%M')}"

            db.create_meeting(
                meeting_id=meeting_id,
                title=normalized_title,
                date=now.strftime("%Y-%m-%d"),
                source_file=os.path.basename(audio_path),
            )

            embeddings = self.embed(segments)
            db.ingest_transcript(segments, embeddings, meeting_id=meeting_id)

            # --- Step 3: LLM 추출 ---
            logger.info("   Step 3: 핵심 정보(토픽/할일) 추출 중...")
            analysis_data = self.extract(transcript_text)

            # --- Step 4: 지식 그래프 적재 ---
            logger.info("   Step 4: 지식 그래프(Knowledge Graph) 구축...")
            db.ingest_data(analysis_data, meeting_id=meeting_id)

        logger.info("✅ [Pipeline] 모든 분석 및 저장이 완료되었습니다.")
        # AnalysisResult → dict 변환 (하위 호환)
        if hasattr(analysis_data, "to_dict"):
            return analysis_data.to_dict()
        return analysis_data

    # ================================================================
    # 🤖 Agent 생성 — Phase 4
    # ================================================================

    def create_agent(self, db_path: str | None = None) -> "SpeakNodeAgent":
        """
        해당 DB에 연결된 AI Agent 인스턴스를 반환합니다.
        Whisper/Embedding 모델을 로딩하지 않고 Agent만 생성합니다.
        """
        from core.agent.agent import SpeakNodeAgent

        target_db_path = db_path or self.config.get_chat_db_path()
        return SpeakNodeAgent(db_path=target_db_path, config=self.config)


if __name__ == "__main__":
    engine = SpeakNodeEngine()
