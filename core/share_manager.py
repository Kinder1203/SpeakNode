import json
import textwrap
from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo
import os

class ShareManager:
    def __init__(self, output_dir="../shared_cards"):
        # 이미지가 저장될 폴더 생성
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        self.output_dir = output_dir

    def create_card(self, data, filename="meeting_card.png"):
        """
        데이터를 시각화한 이미지 카드를 생성하고, 메타데이터에 원본 JSON을 숨김 (ComfyUI 방식)
        """
        # 1. 캔버스 생성 (검은색 배경)
        width, height = 800, 600
        img = Image.new('RGB', (width, height), color=(30, 30, 30))
        draw = ImageDraw.Draw(img)

        # 2. 텍스트 그리기 (간단한 시각화)
        try:
            # [수정] 리눅스에 설치된 나눔고딕 폰트 경로 지정
            font_path = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"
            
            # 제목용 큰 폰트 (크기 40)
            font_title = ImageFont.truetype(font_path, 40)
            # 본문용 작은 폰트 (크기 20)
            font_text = ImageFont.truetype(font_path, 20)
        except Exception as e:
            # 폰트 못 찾으면 기본 폰트 사용 (한글 깨짐)
            print(f"⚠️ 폰트 로드 실패: {e}")
            font_title = ImageFont.load_default()
            font_text = ImageFont.load_default()

        # 제목 추출
        topics = data.get("topics", [])
        title_text = topics[0]['title'] if topics else "No Topic"
        summary_text = topics[0].get('summary', '') if topics else ""

        # 화면에 글씨 쓰기 (영어/숫자는 잘 나오지만 한글은 폰트 없으면 네모로 나올 수 있음)
        draw.text((50, 50), f"SpeakNode Summary", fill=(0, 255, 127)) # 로고색
        draw.text((50, 100), f"Topic: {title_text}", fill=(255, 255, 255))
        
        # 요약문 줄바꿈 처리
        lines = textwrap.wrap(summary_text, width=40)
        y_text = 150
        for line in lines[:10]: # 최대 10줄만 표시
            draw.text((50, y_text), line, fill=(200, 200, 200))
            y_text += 20

        # 3. 핵심: 메타데이터에 JSON 숨기기 (Steganography)
        metadata = PngInfo()
        json_str = json.dumps(data, ensure_ascii=False)
        metadata.add_text("speaknode_data", json_str) # 'speaknode_data'라는 태그에 숨김

        # 4. 저장
        save_path = os.path.join(self.output_dir, filename)
        img.save(save_path, "PNG", pnginfo=metadata)
        print(f"🖼️ [Share] 이미지 카드 생성 완료: {save_path}")
        return save_path

    def load_data_from_image(self, image_path):
        """
        이미지 안에 숨겨진 SpeakNode 데이터를 추출
        """
        try:
            img = Image.open(image_path)
            # 메타데이터 확인
            json_str = img.text.get("speaknode_data")
            
            if json_str:
                print(f"🔓 [Share] 이미지에서 데이터 추출 성공!")
                return json.loads(json_str)
            else:
                print(f"⚠️ [Share] 이 이미지는 SpeakNode 데이터가 없습니다.")
                return None
        except Exception as e:
            print(f"❌ [Share] 이미지 읽기 실패: {e}")
            return None

# 테스트 코드
if __name__ == "__main__":
    manager = ShareManager()
    # 더미 데이터로 테스트
    dummy_data = {"topics": [{"title": "Test Project", "summary": "This is a hidden message."}]}
    
    # 1. 생성 테스트
    path = manager.create_card(dummy_data, "test_card.png")
    
    # 2. 추출 테스트
    extracted = manager.load_data_from_image(path)
    print("Extracted Data:", extracted)