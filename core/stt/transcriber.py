import logging
import os

import torch
from faster_whisper import WhisperModel

from core.config import SpeakNodeConfig

logger = logging.getLogger(__name__)

class Transcriber:
    def __init__(self, config: SpeakNodeConfig = None, model_size=None, device=None):
        cfg = config or SpeakNodeConfig()
        self.config = cfg
        self.language = cfg.whisper_language
        self.beam_size = cfg.whisper_beam_size
        _model_size = model_size or cfg.whisper_model

        # Auto-detect device
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        compute_type = "float16" if self.device == "cuda" else "int8"

        logger.info("Loading Whisper '%s' on %s (%s)...", _model_size, self.device, compute_type)

        try:
            self.model = WhisperModel(
                _model_size,
                device=self.device,
                compute_type=compute_type
            )
            logger.info("Whisper model ready.")
        except Exception as e:
            logger.critical("Failed to load Whisper model: %s", e)
            raise

        # Optional speaker diarization
        self.diarization_pipeline = None
        if cfg.enable_diarization and cfg.hf_token:
            try:
                from pyannote.audio import Pipeline as DiarizationPipeline
                logger.info("Loading speaker diarization model...")
                self.diarization_pipeline = DiarizationPipeline.from_pretrained(
                    "pyannote/speaker-diarization-3.1",
                    use_auth_token=cfg.hf_token,
                )
                if self.device == "cuda":
                    self.diarization_pipeline.to(torch.device("cuda"))
                logger.info("Diarization model ready.")
            except ImportError:
                logger.warning("pyannote.audio not installed; diarization disabled.")
            except Exception as e:
                logger.warning("Diarization load failed (continuing): %s", e)

    def _assign_speakers(self, segments: list[dict], diarization_result) -> list[dict]:
        """Match diarization turns to STT segments by timestamp overlap."""
        for seg in segments:
            seg_mid = (seg["start"] + seg["end"]) / 2.0
            best_speaker = "Unknown"
            best_overlap = 0.0

            for turn, _, speaker in diarization_result.itertracks(yield_label=True):
                # Check if segment midpoint falls within this diarization turn
                overlap_start = max(seg["start"], turn.start)
                overlap_end = min(seg["end"], turn.end)
                overlap = max(0.0, overlap_end - overlap_start)

                if overlap > best_overlap:
                    best_overlap = overlap
                    best_speaker = speaker

            seg["speaker"] = best_speaker
        return segments

    def transcribe(self, audio_path: str) -> list[dict] | None:
        """Transcribe an audio file and return timestamped segments."""
        if not os.path.exists(audio_path):
            logger.error("File not found: %s", audio_path)
            return None

        logger.info("Processing: %s", os.path.basename(audio_path))
        
        # Transcribe
        segments, info = self.model.transcribe(
            audio_path,
            beam_size=self.beam_size,
            language=self.language,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=1000,
                threshold=0.3
            ),
            condition_on_previous_text=True
        )
        logger.info("Detected language: '%s' (prob: %.2f)", info.language, info.language_probability)
        
        # Convert generator to list
        result_data = []
        for segment in segments:
            if segment.text.strip():
                logger.debug("[%.2fs -> %.2fs] %s", segment.start, segment.end, segment.text)
                
                result_data.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip()
                })
        
        # Apply speaker diarization if enabled
        if self.diarization_pipeline and result_data:
            try:
                logger.info("Running speaker diarization...")
                diarization_result = self.diarization_pipeline(audio_path)
                result_data = self._assign_speakers(result_data, diarization_result)
                speaker_set = set(seg.get("speaker", "Unknown") for seg in result_data)
                logger.info("Diarization complete. Speakers: %s", speaker_set)
            except Exception as e:
                logger.warning("Diarization failed (STT results preserved): %s", e)

        logger.info("Transcription complete. Total segments: %d", len(result_data))
        return result_data


if __name__ == "__main__":
    TEST_FILE = "test_audio.mp3"
    if os.path.exists(TEST_FILE):
        stt_engine = Transcriber(model_size="large-v3")
        results = stt_engine.transcribe(TEST_FILE)
        print(results[:] if results else "No result")
    else:
        print(f"'{TEST_FILE}' not found.")