import os
import torch
from faster_whisper import WhisperModel
from core.config import SpeakNodeConfig

class Transcriber:
    def __init__(self, config: SpeakNodeConfig = None, model_size=None, device=None):
        """
        Whisper 모델 초기화 (서버 구동 시 1회 실행됨)
        config가 주어지면 config 우선, 아니면 개별 인자 사용 (역호환)
        """
        cfg = config or SpeakNodeConfig()
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
        
        print(f"🚀 [Transcriber] Loading model '{_model_size}' on {self.device} ({compute_type})...")
        
        try:
            # 모델 로드 (다운로드 및 캐싱 자동 처리)
            self.model = WhisperModel(
                _model_size, 
                device=self.device, 
                compute_type=compute_type
            )
            print(f"✅ [Transcriber] Model loaded ready.")
        except Exception as e:
            print(f"❌ [Transcriber] Critical Error loading model: {e}")
            raise e

    def transcribe(self, audio_path):
        """
        오디오 파일 경로를 받아 텍스트와 메타데이터 반환
        """
        if not os.path.exists(audio_path):
            print(f"⚠️ [Error] File not found: {audio_path}")
            return None

        print(f"🎧 [Transcriber] Processing audio: {os.path.basename(audio_path)}")
        
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
        print(f"   ℹ️ Detected language: '{info.language}' (Probability: {info.language_probability:.2f})")
        
        # Generator를 리스트로 변환 (DB 저장용 포맷팅)
        result_data = []
        for segment in segments:
            # 텍스트가 비어있지 않은 경우만 처리
            if segment.text.strip():
                # 콘솔에 진행 상황 실시간 출력 (디버깅용)
                print(f"   [{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")
                
                result_data.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip()
                })
        
        print(f"✅ [Transcriber] Completed. Total segments: {len(result_data)}")
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