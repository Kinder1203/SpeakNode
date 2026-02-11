import os
import json

try:
    # 1. Streamlit(외부)에서 실행될 때: "내 옆(.)에 있는 파일"이라고 명시
    from .transcriber import Transcriber
    from .extractor import Extractor
    from .kuzu_manager import KuzuManager
    from .share_manager import ShareManager
except ImportError:
    # 2. pipeline.py 직접 실행할 때: "그냥 이름"으로 찾음
    from transcriber import Transcriber
    from extractor import Extractor
    from kuzu_manager import KuzuManager
    from share_manager import ShareManager

def main(audio_path):
    print(f"🚀 [SpeakNode] 파이프라인 시작: {audio_path}")
    
    # 1. 초기화
    transcriber = Transcriber()
    extractor = Extractor()
    db_manager = KuzuManager()

    # 2. STT (듣기)
    print("👂 음성 인식 중...")
    transcript_list = transcriber.transcribe(audio_path)
    # transcript_list는 [{"start":..., "text":...}, ...] 형태의 리스트임

    if not transcript_list:
        print("❌ 음성 인식 결과가 없습니다.")
        return

    # [수정] 리스트에 있는 모든 문장을 하나로 합침
    full_text = " ".join([seg['text'] for seg in transcript_list])
    print(f"📝 추출된 텍스트 길이: {len(full_text)}자")
    
    # 3. LLM Extraction (생각하기)
    print("🧠 회의 내용 분석 중...")
    analysis_result = extractor.extract(full_text) # 합친 텍스트를 전달
    
    # 4. DB Ingestion (기억하기)
    print("💾 그래프 DB에 저장 중...")
    db_manager.ingest_data(analysis_result)

    #5. 공유용 이미지 생성 (Phase 4)
    print("🖼️ 공유용 이미지 카드 생성 중...")
    share_manager = ShareManager()
    share_manager.create_card(analysis_result, filename="latest_summary.png")
    
    print("✅ 모든 작업 완료!")
    return analysis_result

if __name__ == "__main__":
    target_file = "../test_audio.mp3" 
    if os.path.exists(target_file):
        main(target_file)
    else:
        print(f"파일을 찾을 수 없습니다: {target_file}")