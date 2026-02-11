import sys
import os
import shutil
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

# [경로 설정] 프로젝트 루트를 sys.path에 추가 (Core 모듈을 찾기 위해)
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../"))
sys.path.append(project_root)

# Core 모듈 로딩
try:
    from core.pipeline import main as run_pipeline
    from core.share_manager import ShareManager
    print("✅ Core module loaded successfully.")
except ImportError as e:
    print(f"❌ Failed to load Core module: {e}")
    sys.exit(1)

# 앱 초기화
app = FastAPI(title="SpeakNode Brain Server 🧠", version="1.0.0")

# CORS 설정 (Kotlin 앱이나 외부 웹에서 접속 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health_check():
    """서버 생존 확인용"""
    return {"status": "active", "message": "SpeakNode Brain is Ready! 🚀"}

@app.post("/analyze")
async def analyze_audio(file: UploadFile = File(...)):
    """
    [핵심 기능] 오디오 파일 업로드 -> STT/LLM 분석 -> 결과 반환
    """
    temp_filename = os.path.join(project_root, f"temp_{file.filename}")
    
    try:
        # 1. 파일 저장
        with open(temp_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        print(f"📥 Received file: {file.filename}")

        # 2. 파이프라인 실행 (Core Logic)
        result_json = run_pipeline(temp_filename)

        # 3. 결과 반환
        return {
            "status": "success",
            "data": result_json,
            "image_url": "/latest_card" # 생성된 이미지 다운로드 경로 안내
        }

    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        return HTTPException(status_code=500, detail=str(e))
        
    finally:
        # 4. 임시 파일 청소
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

@app.get("/latest_card")
async def get_latest_card():
    """방금 생성된 요약 카드 이미지 다운로드"""
    card_path = os.path.join(project_root, "shared_cards", "latest_summary.png")
    if os.path.exists(card_path):
        return FileResponse(card_path)
    return HTTPException(status_code=404, detail="이미지가 아직 없습니다.")

@app.post("/import_card")
async def import_card(file: UploadFile = File(...)):
    """이미지 업로드 -> 숨겨진 데이터 추출 (Steganography)"""
    temp_img = os.path.join(project_root, f"temp_import_{file.filename}")
    
    try:
        with open(temp_img, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        manager = ShareManager()
        hidden_data = manager.load_data_from_image(temp_img)
        
        if hidden_data:
            # TODO: 여기서 DB에 Merge 하는 로직 추가 가능
            return {"status": "success", "data": hidden_data}
        else:
            return {"status": "failed", "message": "No hidden data found"}
            
    finally:
        if os.path.exists(temp_img):
            os.remove(temp_img)

if __name__ == "__main__":
    import uvicorn
    # 0.0.0.0으로 열어야 외부 접속 가능
    uvicorn.run(app, host="0.0.0.0", port=8000)