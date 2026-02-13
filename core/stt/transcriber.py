import logging
import os

import torch
from faster_whisper import WhisperModel

from core.config import SpeakNodeConfig

logger = logging.getLogger(__name__)

class Transcriber:
    def __init__(self, config: SpeakNodeConfig = None, model_size=None, device=None):
        """
        Whisper 모델 초기화 (서버 구동 시 1회 실행됨)
        config가 주어지면 config 우선, 아니면 개별 인자 사용 (역호환)
        """
        cfg = config or SpeakNodeConfig()
        self.config = cfg
        self.language = cfg.whisper_language
        self.beam_size = cfg.whisper_beam_size
        _model_size = model_size or cfg.whisper_model

        # 디바이스 자동 감지 (RunPod GPU 우선)
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
            
        # GPU 사용 시 float16, CPU 사용 시 int8 (속도 최적화)
        compute_type = "float16" if self.device == "cuda" else "int8"
        
        logger.info("🚀 [Transcriber] Loading model '%s' on %s (%s)...", _model_size, self.device, compute_type)
        
        try:
            # 모델 로드 (다운로드 및 캐싱 자동 처리)
            self.model = WhisperModel(
                _model_size, 
                device=self.device, 
                compute_type=compute_type
            )
            logger.info("✅ [Transcriber] Model loaded ready.")
        except Exception as e:
            logger.critical("❌ [Transcriber] Critical Error loading model: %s", e)
            raise

        # --- 화자 분리(Diarization) 초기화 (선택적) ---
        self.diarization_pipeline = None
        if cfg.enable_diarization and cfg.hf_token:
            try:
                from pyannote.audio import Pipeline as DiarizationPipeline
                logger.info("🎙️ [Transcriber] Loading Speaker Diarization model...")
                self.diarization_pipeline = DiarizationPipeline.from_pretrained(
                    "pyannote/speaker-diarization-3.1",
                    use_auth_token=cfg.hf_token,
                )
                if self.device == "cuda":
                    self.diarization_pipeline.to(torch.device("cuda"))
                logger.info("✅ [Transcriber] Diarization model loaded.")
            except ImportError:
                logger.warning("⚠️ [Transcriber] pyannote.audio 미설치. 화자 분리 비활성화.")
            except Exception as e:
                logger.warning("⚠️ [Transcriber] Diarization 로드 실패 (계속 진행): %s", e)

    def _assign_speakers(self, segments: list[dict], diarization_result) -> list[dict]:
        """
        Diarization 결과와 STT 세그먼트의 타임스탬프를 매칭하여
        각 세그먼트에 speaker 필드를 할당합니다.
        """
        for seg in segments:
            seg_mid = (seg["start"] + seg["end"]) / 2.0
            best_speaker = "Unknown"
            best_overlap = 0.0

            for turn, _, speaker in diarization_result.itertracks(yield_label=True):
                # 세그먼트 중간점이 diarization turn 안에 있는지 확인
                overlap_start = max(seg["start"], turn.start)
                overlap_end = min(seg["end"], turn.end)
                overlap = max(0.0, overlap_end - overlap_start)

                if overlap > best_overlap:
                    best_overlap = overlap
                    best_speaker = speaker

            seg["speaker"] = best_speaker
        return segments

    def transcribe(self, audio_path: str) -> list[dict] | None:
        """
        오디오 파일 경로를 받아 텍스트와 메타데이터 반환
        """
        if not os.path.exists(audio_path):
            logger.error("⚠️ [Error] File not found: %s", audio_path)
            return None

        logger.info("🎧 [Transcriber] Processing audio: %s", os.path.basename(audio_path))
        
        # Transcribe 실행
        segments, info = self.model.transcribe(
            audio_path, 
            beam_size=self.beam_size, 
            language=self.language,
            # 1. VAD 필터를 끄거나, 임계값을 조절합니다.
            vad_filter=True, 
            vad_parameters=dict(
                min_silence_duration_ms=1000, # 1초 이상 조용해야 분리 (기존 500ms는 너무 짧음)
                threshold=0.3                # 소리가 작아도 음성으로 인식하도록 문턱값 낮춤
            ),
            # 2. 문장 중간에 끊기는 걸 방지하기 위해 추가
            condition_on_previous_text=True 
        )  
        logger.info("   ℹ️ Detected language: '%s' (Probability: %.2f)", info.language, info.language_probability)
        
        # Generator를 리스트로 변환 (DB 저장용 포맷팅)
        result_data = []
        for segment in segments:
            # 텍스트가 비어있지 않은 경우만 처리
            if segment.text.strip():
                # 콘솔에 진행 상황 실시간 출력 (디버깅용)
                logger.debug("   [%.2fs -> %.2fs] %s", segment.start, segment.end, segment.text)
                
                result_data.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip()
                })
        
        # --- 화자 분리 적용 (활성화된 경우) ---
        if self.diarization_pipeline and result_data:
            try:
                logger.info("🎙️ [Transcriber] 화자 분리 수행 중...")
                diarization_result = self.diarization_pipeline(audio_path)
                result_data = self._assign_speakers(result_data, diarization_result)
                speaker_set = set(seg.get("speaker", "Unknown") for seg in result_data)
                logger.info("✅ [Transcriber] 화자 분리 완료. 감지된 화자: %s", speaker_set)
            except Exception as e:
                logger.warning("⚠️ [Transcriber] 화자 분리 실패 (STT 결과는 유지): %s", e)

        logger.info("✅ [Transcriber] Completed. Total segments: %d", len(result_data))
        return result_data

# ==========================================
# 🧪 테스트 실행 코드 (RunPod에서 직접 실행 시 동작)
# ==========================================
if __name__ == "__main__":
    # 1. 테스트용 파일 경로 (runpodctl로 올린 파일 이름)
    TEST_FILE = "test_audio.mp3"  # 같은 폴더에 있다고 가정
    
    if os.path.exists(TEST_FILE):
        # 2. 모델 초기화 (가장 강력한 large-v3 모델 사용)
        # RunPod VRAM이 충분하므로 large-v3 권장
        stt_engine = Transcriber(model_size="large-v3")
        
        # 3. 변환 수행
        results = stt_engine.transcribe(TEST_FILE)
        
        # 4. 결과 확인
        print("\n--- [Final Result Sample] ---")
        print(results[:] if results else "No result") # 앞부분 3개만 출력
    else:
        print(f"❌ '{TEST_FILE}' not found. Please upload it via runpodctl.")
        print("Tip: runpodctl send test_audio.mp3")