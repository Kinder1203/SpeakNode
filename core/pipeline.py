import os
import time
# 우리가 만든 부품들 가져오기
from core.transcriber import Transcriber
from core.extractor import Extractor

class MeetingPipeline:
    def __init__(self):
        print("🔧 [Pipeline] Initializing AI Engine...")
        
        # 1. 귀 장착 (STT) - GPU 사용
        self.ear = Transcriber(model_size="large-v3")
        
        # 2. 뇌 장착 (LLM) - RunPod 내부 Ollama 사용
        # (RunPod 내부에서 도는 거라 localhost로 연결하면 됨)
        self.brain = Extractor(model_name="deepseek-r1:14b")
        
        print("✅ [Pipeline] Engine Ready!")

    def process_meeting(self, audio_path):
        """
        오디오 -> 텍스트 -> 구조화 데이터 (Full Process)
        """
        start_time = time.time()
        print(f"\n🚀 [Pipeline] Processing Start: {audio_path}")

        # Step 1: 듣기 (Transcribe)
        transcript_segments = self.ear.transcribe(audio_path)
        if not transcript_segments:
            return None

        # Step 2: 텍스트 합치기 (LLM에게 줄 요약본 만들기)
        # (세그먼트들을 하나의 긴 문자열로 합침)
        full_text = " ".join([seg['text'] for seg in transcript_segments])
        print(f"📜 [Pipeline] Full Text Length: {len(full_text)} chars")

        # Step 3: 생각하기 (Extract)
        structured_data = self.brain.extract(full_text)

        # Step 4: 결과 정리
        final_result = {
            "meta": {
                "audio_file": os.path.basename(audio_path),
                "processing_time": round(time.time() - start_time, 2),
                "transcript_length": len(transcript_segments)
            },
            "transcript": transcript_segments, # 원본 대화 내용 (타임스탬프 포함)
            "analysis": structured_data        # 분석된 내용 (주제, 할일 등)
        }

        print(f"✨ [Pipeline] All Done in {final_result['meta']['processing_time']}s")
        return final_result

# ==========================================
# 🧪 최종 통합 테스트
# ==========================================
if __name__ == "__main__":
    # 테스트 파일 (아까 이름 바꾼 그 파일)
    TEST_FILE = "test_audio.mp3"
    
    if os.path.exists(TEST_FILE):
        pipeline = MeetingPipeline()
        result = pipeline.process_meeting(TEST_FILE)
        
        import json
        print("\n🎉 [Final Pipeline Result] 🎉")
        # 한글 깨짐 방지해서 예쁘게 출력
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"❌ File not found: {TEST_FILE}")