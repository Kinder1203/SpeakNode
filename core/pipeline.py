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

    def process(self, audio_path: str, db_path: str | None = None, meeting_title: str | None = None):
        """Full pipeline: STT -> Embedding -> LLM extraction -> DB ingest."""
        logger.info("Pipeline started: %s", os.path.basename(audio_path))

        # Step 1: STT
        segments = self.transcribe(audio_path)
        if not segments:
            return None

        transcript_text = " ".join([seg.get("text", "") for seg in segments]).strip()
        if not transcript_text or transcript_text.lower() in ("none", "[]"):
            logger.warning("No valid text in transcript.")
            return None

        # Step 2: Embedding
        logger.info("Embedding segments...")
        target_db_path = db_path if db_path else self.config.get_chat_db_path()

        # Run embedding before opening DB to avoid orphan Meeting nodes on failure.
        embeddings = self.embed(segments)

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
            logger.info("Extracting topics/tasks...")
            try:
                analysis_data = self.extract(transcript_text)
            except Exception:
                logger.exception("LLM extraction failed; utterance data preserved.")
                analysis_data = None

            if not analysis_data:
                logger.warning("LLM extraction returned no results.")
                return {"topics": [], "decisions": [], "tasks": [], "people": [], "entities": [], "relations": []}

            # Step 4: Knowledge graph ingest
            logger.info("Building knowledge graph...")
            db.ingest_data(analysis_data, meeting_id=meeting_id)

        logger.info("Pipeline complete.")
        # AnalysisResult -> dict (backward compat)
        if hasattr(analysis_data, "to_dict"):
            return analysis_data.to_dict()
        return analysis_data

    def create_agent(self, db_path: str | None = None) -> "SpeakNodeAgent":
        """Create an Agent instance bound to the given DB."""
        from core.agent.agent import SpeakNodeAgent

        target_db_path = db_path or self.config.get_chat_db_path()
        return SpeakNodeAgent(db_path=target_db_path, config=self.config)


if __name__ == "__main__":
    engine = SpeakNodeEngine()
