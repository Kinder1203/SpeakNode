import json
import logging
import textwrap
import base64
import zlib
from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo
import os

logger = logging.getLogger(__name__)

MAX_EMBEDDED_PAYLOAD_BYTES = 32 * 1024 * 1024


class ShareManager:
    def __init__(self, output_dir="../shared_cards"):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        self.output_dir = output_dir

    def create_card(self, data: dict, filename: str = "meeting_card.png") -> str:
        """
        데이터를 시각화한 이미지 카드를 생성하고, 메타데이터에 원본 JSON을 숨김
        """
        # 1. 캔버스 생성
        width, height = 800, 600
        img = Image.new('RGB', (width, height), color=(30, 30, 30))
        draw = ImageDraw.Draw(img)

        # 2. 폰트 설정 (OS 호환)
        font_path = None
        try:
            if os.name == 'posix':  # Linux (RunPod 등)
                # 나눔고딕 우선 시도, 없으면 데자뷰 등 대체 폰트 탐색
                candidates = [
                    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
                ]
                for path in candidates:
                    if os.path.exists(path):
                        font_path = path
                        break
            elif os.name == 'nt':  # Windows
                # 윈도우 기본 폰트
                font_path = "C:/Windows/Fonts/malgun.ttf"
            
            if font_path:
                font_title = ImageFont.truetype(font_path, 40)
                font_text = ImageFont.truetype(font_path, 20)
            else:
                raise FileNotFoundError("No suitable font found.")
                
        except Exception as e:
            logger.warning("⚠️ 폰트 로드 실패(%s). 기본 폰트를 사용합니다 (한글 깨짐 가능성 있음).", e)
            font_title = ImageFont.load_default()
            font_text = ImageFont.load_default()

        # 제목 추출
        topics = data.get("topics", [])
        title_text = topics[0]['title'] if topics else "No Topic"
        summary_text = topics[0].get('summary', '') if topics else ""

        # 화면에 글씨 쓰기
        draw.text((50, 50), f"SpeakNode Summary", fill=(0, 255, 127), font=font_title)
        draw.text((50, 100), f"Topic: {title_text}", fill=(255, 255, 255), font=font_text)
        
        # 요약문 줄바꿈 처리
        lines = textwrap.wrap(summary_text, width=40)
        y_text = 150
        for line in lines[:10]: # 최대 10줄만 표시
            draw.text((50, y_text), line, fill=(200, 200, 200), font=font_text)
            y_text += 30 # 줄 간격 조정

        # 3. 메타데이터에 JSON 숨기기
        metadata = PngInfo()
        metadata.add_text("speaknode_data_zlib_b64", self._encode_payload(data))

        # 4. 저장
        save_path = os.path.join(self.output_dir, filename)
        img.save(save_path, "PNG", pnginfo=metadata)
        logger.info("🖼️ [Share] 이미지 카드 생성 완료: %s", save_path)
        return save_path

    def load_data_from_image(self, image_path: str) -> dict | None:
        """이미지 안에 숨겨진 SpeakNode 데이터를 추출"""
        try:
            img = Image.open(image_path)
            compressed = img.text.get("speaknode_data_zlib_b64")
            legacy_json = img.text.get("speaknode_data")

            if compressed:
                logger.info("🔓 [Share] 이미지에서 압축 데이터 추출 성공!")
                return self._decode_payload(compressed)
            if legacy_json:
                logger.info("🔓 [Share] 이미지에서 데이터 추출 성공!")
                return json.loads(legacy_json)

            logger.warning("⚠️ [Share] 이 이미지는 SpeakNode 데이터가 없습니다.")
            return None
        except Exception as e:
            logger.error("❌ [Share] 이미지 읽기 실패: %s", e)
            return None

    @staticmethod
    def _encode_payload(data) -> str:
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        compressed = zlib.compress(raw, level=9)
        return base64.b64encode(compressed).decode("ascii")

    @staticmethod
    def _decode_payload(encoded: str):
        compressed = base64.b64decode(encoded.encode("ascii"))
        decompressor = zlib.decompressobj()
        raw_part = decompressor.decompress(compressed, MAX_EMBEDDED_PAYLOAD_BYTES + 1)
        if len(raw_part) > MAX_EMBEDDED_PAYLOAD_BYTES:
            raise ValueError("Embedded payload exceeds maximum allowed size")
        if decompressor.unconsumed_tail:
            raise ValueError("Embedded payload is too large or malformed")
        raw_part += decompressor.flush()
        if len(raw_part) > MAX_EMBEDDED_PAYLOAD_BYTES:
            raise ValueError("Embedded payload exceeds maximum allowed size")
        return json.loads(raw_part.decode("utf-8"))
