import os
import sys

# 프로젝트 루트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../"))
if project_root not in sys.path:
    sys.path.append(project_root)

from core.transcriber import Transcriber
from core.extractor import Extractor
from core.kuzu_manager import KuzuManager

class SpeakNodeEngine:
    """
    SpeakNode AI 엔진 (Singleton 패턴)
    """
    def __init__(self):
        print("🚀 [System] 엔진 초기화 중... (모델 로딩)")
        self.transcriber = Transcriber(model_size="large-v3") 
        self.extractor = Extractor(model_name="qwen2.5:14b")
        # DB 경로를 절대 경로로 미리 계산
        self.db_path = os.path.join(project_root, "database", "speaknode.kuzu")
        print("✅ [System] 엔진 준비 완료!")

    def process(self, audio_path: str):
        print(f"▶️ [Pipeline] 분석 시작: {os.path.basename(audio_path)}")
        
        # 1. STT 변환
        print("   Processing Step 1: STT...")
        stt_result = self.transcriber.transcribe(audio_path)
        
        # [Check 1] STT 결과가 None인 경우 즉시 중단
        if stt_result is None:
            print("❌ [Pipeline] STT 반환값이 없습니다 (None). 분석을 중단합니다.")
            return None

        transcript_text = ""
        
        # [Fix: Critical] 리스트 처리 로직 보강 (빈 리스트 '[]' 문자열화 방지)
        if isinstance(stt_result, list):
            if not stt_result: # 빈 리스트인 경우
                transcript_text = "" # 명시적으로 빈 문자열 할당
            elif isinstance(stt_result[0], dict):
                transcript_text = " ".join([seg.get('text', '') for seg in stt_result])
            elif hasattr(stt_result[0], 'text'):
                transcript_text = " ".join([seg.text for seg in stt_result])
            else:
                transcript_text = str(stt_result)
                
        elif isinstance(stt_result, dict):
            transcript_text = stt_result.get('text', "")
        else:
            transcript_text = str(stt_result)
        
        # [Check 2] 텍스트 유효성 재확인 (빈 문자열, "None", "[]" 등 방어)
        cleaned_text = transcript_text.strip()
        if not cleaned_text or cleaned_text.lower() == "none" or cleaned_text == "[]":
            print(f"⚠️ [Warning] 유효한 텍스트가 없습니다. (Raw: {transcript_text})")
            return None

        # 2. LLM 정보 추출
        print("   Processing Step 2: LLM Extraction...")
        analysis_data = self.extractor.extract(transcript_text)
        
        # 3. DB 적재
        print("   Processing Step 3: Knowledge Graph Ingestion...")
        db = KuzuManager(db_path=self.db_path)
        try:
            db.ingest_data(analysis_data)
        finally:
            db.close() # 작업 완료 후 명시적으로 닫기
        
        print("✅ [Pipeline] 분석 및 저장 완료")
        return analysis_data

if __name__ == "__main__":
    engine = SpeakNodeEngine()