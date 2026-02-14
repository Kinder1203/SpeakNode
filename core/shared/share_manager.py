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
        """Generate a summary card image with the raw data embedded in PNG metadata."""
        # Sanitise filename
        safe_filename = os.path.basename(filename) or "meeting_card.png"

        width, height = 800, 600
        img = Image.new('RGB', (width, height), color=(30, 30, 30))
        draw = ImageDraw.Draw(img)

        # Font setup (OS-aware)
        font_path = None
        try:
            if os.name == 'posix':
                candidates = [
                    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
                ]
                for path in candidates:
                    if os.path.exists(path):
                        font_path = path
                        break
            elif os.name == 'nt':
                font_path = "C:/Windows/Fonts/malgun.ttf"
            
            if font_path:
                font_title = ImageFont.truetype(font_path, 40)
                font_text = ImageFont.truetype(font_path, 20)
            else:
                raise FileNotFoundError("No suitable font found.")
                
        except Exception as e:
            logger.warning("Font load failed (%s). Using default (CJK may break).", e)
            font_title = ImageFont.load_default()
            font_text = ImageFont.load_default()

        # Extract title
        topics = data.get("topics", [])
        title_text = topics[0]['title'] if topics else "No Topic"
        summary_text = topics[0].get('summary', '') if topics else ""

        # Draw text
        draw.text((50, 50), f"SpeakNode Summary", fill=(0, 255, 127), font=font_title)
        draw.text((50, 100), f"Topic: {title_text}", fill=(255, 255, 255), font=font_text)
        
        # Wrap summary
        lines = textwrap.wrap(summary_text, width=40)
        y_text = 150
        for line in lines[:10]:
            draw.text((50, y_text), line, fill=(200, 200, 200), font=font_text)
            y_text += 30

        # Embed JSON payload in PNG metadata
        metadata = PngInfo()
        metadata.add_text("speaknode_data_zlib_b64", self._encode_payload(data))

        # Save
        save_path = os.path.join(self.output_dir, safe_filename)
        img.save(save_path, "PNG", pnginfo=metadata)
        logger.info("Share card created: %s", save_path)
        return save_path

    def load_data_from_image(self, image_path: str) -> dict | None:
        """Extract embedded SpeakNode data from a PNG image."""
        try:
            img = Image.open(image_path)
            compressed = img.text.get("speaknode_data_zlib_b64")
            legacy_json = img.text.get("speaknode_data")

            if compressed:
                logger.info("Compressed payload extracted from image.")
                return self._decode_payload(compressed)
            if legacy_json:
                logger.info("Legacy payload extracted from image.")
                return json.loads(legacy_json)

            logger.warning("No SpeakNode data in this image.")
            return None
        except Exception as e:
            logger.error("Failed to read image: %s", e)
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
