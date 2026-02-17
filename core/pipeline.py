"""SpeakNode Pipeline: STT -> Embedding -> LLM -> Graph DB.

Lazy loading: each module is loaded only on first use.
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
    """Lazy-loading AI engine: STT -> Embedding -> LLM -> DB."""

    def __init__(self, config: SpeakNodeConfig = None):
        self.config = config or SpeakNodeConfig()
        self._transcriber = None
        self._extractor = None
        self._transcriber_init_lock = threading.Lock()
        self._extractor_init_lock = threading.Lock()
        self._transcriber_run_lock = threading.Lock()
        self._embedder_run_lock = threading.Lock()
        self._extractor_run_lock = threading.Lock()
        logger.info("Engine ready (lazy loading enabled)")

    @property
    def transcriber(self):
        if self._transcriber is None:
            with self._transcriber_init_lock:
                if self._transcriber is None:
                    from core.stt.transcriber import Transcriber
                    logger.info("Loading Whisper model...")
                    self._transcriber = Transcriber(config=self.config)
        return self._transcriber

    @property
    def embedder(self):
        return get_embedder(self.config.embedding_model)

    @property
    def extractor(self):
        if self._extractor is None:
            with self._extractor_init_lock:
                if self._extractor is None:
                    from core.llm.extractor import Extractor
                    logger.info("Loading LLM extractor...")
                    self._extractor = Extractor(config=self.config)
        return self._extractor
        return self._extractor

    def transcribe(self, audio_path: str) -> list[dict] | None:
        """Run STT on an audio file and return segments."""
        if not os.path.exists(audio_path):
            logger.error("File not found: %s", audio_path)
            return None

        logger.info("STT started: %s", os.path.basename(audio_path))
        with self._transcriber_run_lock:
            result = self.transcriber.transcribe(audio_path)

        if not result:
            logger.error("STT produced no results.")
            return None
        return result

    def embed(self, segments: list[dict]) -> list[list[float]]:
        """Vectorise segment texts in batches."""
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
        """Extract topics, tasks, and decisions from transcript text."""
        with self._extractor_run_lock:
            return self.extractor.extract(transcript_text)

    def process(self, audio_path: str, db_path: str | None = None, meeting_title: str | None = None,
                progress_callback=None):
        """Full pipeline: STT -> Embedding -> LLM extraction -> DB ingest.
        
        Args:
            progress_callback: Optional callable(step: str, percent: int, message: str)
                               for reporting real-time progress.
        """
        def _progress(step: str, percent: int, message: str):
            if progress_callback:
                try:
                    progress_callback(step, percent, message)
                except Exception:
                    pass  # never let callback errors kill the pipeline

        _progress("start", 0, f"파이프라인 시작: {os.path.basename(audio_path)}")
        logger.info("Pipeline started: %s", os.path.basename(audio_path))

        # Step 1: STT
        _progress("stt", 5, "음성 인식 모델 로딩 중...")
        _progress("stt", 10, "음성 인식 중 (STT)...")
        segments = self.transcribe(audio_path)
        if not segments:
            _progress("stt", 15, "음성이 감지되지 않았습니다.")
            return None

        _progress("stt", 20, f"음성 인식 후처리 중 ({len(segments)}개 세그먼트)...")
        _progress("stt", 25, f"음성 인식 완료 ({len(segments)}개 세그먼트)")

        transcript_text = " ".join([seg.get("text", "") for seg in segments]).strip()
        if not transcript_text or transcript_text.lower() in ("none", "[]"):
            logger.warning("No valid text in transcript.")
            return None

        # Step 2: Embedding
        _progress("embedding", 30, "임베딩 생성 중...")
        logger.info("Embedding segments...")
        target_db_path = db_path if db_path else self.config.get_chat_db_path()

        # Run embedding before opening DB to avoid orphan Meeting nodes on failure.
        embeddings = self.embed(segments)
        _progress("embedding", 45, "임베딩 완료")

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

            db.ingest_transcript(segments, embeddings, meeting_id=meeting_id)

            # Step 3: LLM extraction
            _progress("extraction", 50, "LLM 추출 준비 중...")
            _progress("extraction", 55, "LLM으로 주제/할일 추출 중...")
            logger.info("Extracting topics/tasks...")
            try:
                _progress("extraction", 60, "LLM 모델 추론 진행 중...")
                analysis_data = self.extract(transcript_text)
            except Exception:
                logger.exception("LLM extraction failed; utterance data preserved.")
                analysis_data = None

            if not analysis_data:
                logger.warning("LLM extraction returned no results.")
                _progress("extraction", 75, "추출 결과 없음")
                return {
                    "meeting_id": meeting_id,
                    "topics": [], "decisions": [], "tasks": [],
                    "people": [], "entities": [], "relations": [],
                }

            _progress("extraction", 70, "주제/할일 추출 완료")

            # Step 4: Knowledge graph ingest
            _progress("graph", 80, "지식 그래프 구축 중...")
            logger.info("Building knowledge graph...")
            db.ingest_data(analysis_data, meeting_id=meeting_id)
            _progress("graph", 90, "지식 그래프 구축 완료")

        logger.info("Pipeline complete.")
        # AnalysisResult -> dict (backward compat)
        if hasattr(analysis_data, "to_dict"):
            result_dict = analysis_data.to_dict()
        else:
            result_dict = analysis_data if isinstance(analysis_data, dict) else {}
        result_dict["meeting_id"] = meeting_id
        _progress("complete", 100, "파이프라인 완료!")
        return result_dict

    def create_agent(self, db_path: str | None = None) -> "SpeakNodeAgent":
        """Create an Agent instance bound to the given DB."""
        from core.agent.agent import SpeakNodeAgent

        target_db_path = db_path or self.config.get_chat_db_path()
        return SpeakNodeAgent(db_path=target_db_path, config=self.config)


if __name__ == "__main__":
    engine = SpeakNodeEngine()
