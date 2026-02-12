import os
import sys

# 프로젝트 루트 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../"))
if project_root not in sys.path:
    sys.path.append(project_root)

from core.config import SpeakNodeConfig
from core.transcriber import Transcriber
from core.extractor import Extractor
from core.kuzu_manager import KuzuManager
from sentence_transformers import SentenceTransformer

class SpeakNodeEngine:
    """
    SpeakNode AI 엔진 (Singleton 패턴)
    - STT (귀) -> Embedding (이해) -> LLM (지능) -> DB (기억)
    """
    def __init__(self, config: SpeakNodeConfig = None):
        self.config = config or SpeakNodeConfig()
        print("🚀 [System] 엔진 초기화 중...")
        
        # 1. 청각 모듈 (STT)
        print("   Init: Loading Whisper (Ear)...")
        self.transcriber = Transcriber(config=self.config) 
        
        # 2. 이해 모듈 (Embedding)
        print("   Init: Loading Embedding Model (Understanding)...")
        self.embedder = SentenceTransformer(self.config.embedding_model)
        
        # 3. 지능 모듈 (LLM)
        print("   Init: Loading LLM (Brain)...")
        self.extractor = Extractor(config=self.config)
        
        print("✅ [System] 엔진 준비 완료!")

    # ================================================================
    # 📌 개별 단계 — Agent가 독립적으로 호출 가능
    # ================================================================

    def transcribe(self, audio_path: str) -> list[dict] | None:
        """
        Step 1: STT만 수행. 오디오 → 세그먼트 리스트 반환.
        Agent가 STT 결과만 필요할 때 단독 호출 가능.
        """
        if not os.path.exists(audio_path):
            print(f"⚠️ [Error] File not found: {audio_path}")
            return None

        print(f"🎧 [Pipeline] STT 시작: {os.path.basename(audio_path)}")
        result = self.transcriber.transcribe(audio_path)

        if not result:
            print("❌ [Pipeline] STT 실패 또는 결과 없음.")
            return None
        return result

    def embed(self, segments: list[dict]) -> list[list[float]]:
        """
        Step 2: 세그먼트 텍스트를 벡터로 변환.
        Agent가 특정 텍스트의 벡터가 필요할 때 단독 호출 가능.
        """
        texts = [seg["text"] for seg in segments]
        return self.embedder.encode(texts).tolist()

    def extract(self, transcript_text: str) -> dict:
        """
        Step 3: 텍스트에서 Topic/Task/Decision 추출.
        Agent가 텍스트 분석만 필요할 때 단독 호출 가능.
        """
        return self.extractor.extract(transcript_text)

    # ================================================================
    # 🔄 통합 파이프라인 — 전체 흐름 실행 (역호환 유지)
    # ================================================================

    def process(self, audio_path: str, db_path: str | None = None, meeting_title: str | None = None):
        """
        전체 파이프라인: STT → Embedding → LLM → DB 적재
        기존 호출 방식 완전 호환 + meeting_title 옵션 추가.
        """
        print(f"▶️ [Pipeline] 분석 시작: {os.path.basename(audio_path)}")

        # --- Step 1: STT ---
        segments = self.transcribe(audio_path)
        if not segments:
            return None

        # 텍스트 전처리
        transcript_text = " ".join([seg.get("text", "") for seg in segments]).strip()
        if not transcript_text or transcript_text.lower() in ("none", "[]"):
            print(f"⚠️ [Warning] 유효한 텍스트가 없습니다.")
            return None

        # --- Step 2: Embedding + DB 적재 ---
        print("   Step 2: 문맥 벡터화 및 대화 흐름 저장...")
        target_db_path = db_path if db_path else self.config.get_chat_db_path()

        with KuzuManager(db_path=target_db_path, config=self.config) as db:
            # Meeting 생성 (제목이 주어진 경우)
            meeting_id = None
            if meeting_title:
                import datetime
                meeting_id = f"m_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
                db.create_meeting(
                    meeting_id=meeting_id,
                    title=meeting_title,
                    date=datetime.datetime.now().strftime("%Y-%m-%d"),
                    source_file=os.path.basename(audio_path),
                )

            # 2-1. 벡터 생성 + Transcript 적재
            embeddings = self.embed(segments)
            db.ingest_transcript(segments, embeddings, meeting_id=meeting_id)

            # --- Step 3: LLM 추출 ---
            print("   Step 3: 핵심 정보(토픽/할일) 추출 중...")
            analysis_data = self.extract(transcript_text)

            # --- Step 4: 지식 그래프 적재 ---
            print("   Step 4: 지식 그래프(Knowledge Graph) 구축...")
            db.ingest_data(analysis_data, meeting_id=meeting_id)

        print("✅ [Pipeline] 모든 분석 및 저장이 완료되었습니다.")
        return analysis_data

if __name__ == "__main__":
    engine = SpeakNodeEngine()