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
# [New] 문장 임베딩(Vector) 생성을 위한 라이브러리
from sentence_transformers import SentenceTransformer

class SpeakNodeEngine:
    """
    SpeakNode AI 엔진 (Singleton 패턴)
    - STT (귀) -> Embedding (이해) -> LLM (지능) -> DB (기억)
    """
    def __init__(self):
        print("🚀 [System] 엔진 초기화 중...")
        
        # 1. 청각 모듈 (STT)
        print("   Init: Loading Whisper (Ear)...")
        self.transcriber = Transcriber(model_size="large-v3") 
        
        # 2. 이해 모듈 (Embedding) [New]
        # 로컬에서 가장 효율적인 sbert 모델 사용 (384차원)
        print("   Init: Loading Embedding Model (Understanding)...")
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        
        # 3. 지능 모듈 (LLM)
        print("   Init: Loading LLM (Brain)...")
        self.extractor = Extractor(model_name="qwen2.5:14b")
        
        # DB 경로 미리 계산
        self.db_path = os.path.join(project_root, "database", "chats", "default.kuzu")
        print("✅ [System] 엔진 준비 완료!")

    def process(self, audio_path: str, db_path: str | None = None):
        print(f"▶️ [Pipeline] 분석 시작: {os.path.basename(audio_path)}")
        
        # --- Step 1: STT 변환 (귀) ---
        print("   Step 1: 오디오 변환 (STT)...")
        stt_result = self.transcriber.transcribe(audio_path)
        
        if not stt_result:
            print("❌ [Pipeline] STT 실패 또는 결과 없음.")
            return None

        # 텍스트 전처리
        transcript_text = ""
        raw_segments = [] # 임베딩을 위해 원본 세그먼트 보존
        
        if isinstance(stt_result, list):
            raw_segments = stt_result
            if raw_segments:
                transcript_text = " ".join([seg.get('text', '') for seg in raw_segments])
        elif isinstance(stt_result, dict):
            transcript_text = stt_result.get('text', "")
            # dict 형태라면 raw_segments를 구성하기 어려움 (예외 처리)
        else:
            transcript_text = str(stt_result)
        
        cleaned_text = transcript_text.strip()
        if not cleaned_text or cleaned_text.lower() == "none" or cleaned_text == "[]":
            print(f"⚠️ [Warning] 유효한 텍스트가 없습니다.")
            return None

        # --- Step 2: 임베딩 및 기억 저장 (이해 & 기억) [New] ---
        print("   Step 2: 문맥 벡터화 및 대화 흐름 저장...")
        target_db_path = db_path if db_path else self.db_path
        db = KuzuManager(db_path=target_db_path)
        
        try:
            # 2-1. 벡터 생성
            if raw_segments:
                texts = [seg['text'] for seg in raw_segments]
                # encode()는 numpy array를 반환하므로 tolist()로 변환
                embeddings = self.embedder.encode(texts).tolist()
                
                # 2-2. 대화 내용(Transcript) DB 적재
                # (이전 단계에서 만든 ingest_transcript 호출)
                db.ingest_transcript(raw_segments, embeddings)
            else:
                print("   ⚠️ 세그먼트 정보가 없어 대화 흐름 저장을 건너뜁니다.")

            # --- Step 3: LLM 정보 추출 (추론) ---
            print("   Step 3: 핵심 정보(토픽/할일) 추출 중...")
            analysis_data = self.extractor.extract(transcript_text)
            
            # --- Step 4: 지식 그래프 적재 (구조화) ---
            print("   Step 4: 지식 그래프(Knowledge Graph) 구축...")
            db.ingest_data(analysis_data)
            
        finally:
            db.close() # 리소스 해제
        
        print("✅ [Pipeline] 모든 분석 및 저장이 완료되었습니다.")
        return analysis_data

if __name__ == "__main__":
    engine = SpeakNodeEngine()