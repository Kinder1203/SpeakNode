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
        self.extractor = Extractor(model_name="deepseek-r1:14b")
        # DB 경로를 절대 경로로 미리 계산
        self.db_path = os.path.join(project_root, "database", "speaknode.kuzu")
        print("✅ [System] 엔진 준비 완료!")

    def process(self, audio_path: str):
        print(f"▶️ [Pipeline] 분석 시작: {os.path.basename(audio_path)}")
        
        # 1. STT 변환
        print("   Processing Step 1: STT...")
        # [Fix] transcribe 반환값(list) 처리
        # Faster-Whisper는 (segments, info) 혹은 list[Segment]를 반환함.
        # 구현에 따라 다르지만, 리스트인 경우 텍스트를 join해야 함.
        segments_or_text = self.transcriber.transcribe(audio_path)
        
        if isinstance(segments_or_text, list):
            # 세그먼트 리스트인 경우 텍스트 추출 및 결합
            transcript_text = " ".join([seg.text for seg in segments_or_text])
        elif isinstance(segments_or_text, dict) and 'text' in segments_or_text:
            transcript_text = segments_or_text['text']
        else:
            transcript_text = str(segments_or_text)
        
        if not transcript_text.strip():
            print("⚠️ [Warning] 추출된 텍스트가 없습니다.")
            return None

        # 2. LLM 정보 추출
        print("   Processing Step 2: LLM Extraction...")
        # [Fix] 메서드명 불일치 수정 (extract_info -> extract)
        analysis_data = self.extractor.extract(transcript_text)
        
        # 3. DB 적재
        print("   Processing Step 3: Knowledge Graph Ingestion...")
        # [Fix] 절대 경로 주입 (실행 위치 의존성 제거)
        db = KuzuManager(db_path=self.db_path)
        db.ingest_data(analysis_data)
        
        print("✅ [Pipeline] 분석 및 저장 완료")
        return analysis_data

if __name__ == "__main__":
    engine = SpeakNodeEngine()