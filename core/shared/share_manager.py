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
    """PNG 이미지에 SpeakNode 분석 데이터를 임베딩·추출하는 매니저."""

    # ── 카드 렌더링 상수 ──
    _CARD_SIZE = (800, 480)
    _STATUS_COLORS = {
        "pending": (245, 158, 11),
        "in_progress": (6, 182, 212),
        "done": (34, 197, 94),
        "blocked": (239, 68, 68),
    }
    _BADGE_DEFS = [
        ("Topics", "topics", (34, 197, 94)),
        ("People", "people", (168, 85, 247)),
        ("Tasks", "tasks", (245, 158, 11)),
        ("Decisions", "decisions", (244, 114, 182)),
        ("Entities", "entities", (236, 72, 153)),
    ]

    def __init__(self, output_dir="../shared_cards"):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        self.output_dir = output_dir

    # ── 내부: 폰트 로딩 ──
    @staticmethod
    def _load_fonts() -> dict:
        """OS별 CJK 호환 폰트를 5종 사이즈로 로딩한다."""
        if os.name == "nt":
            candidates = [
                "C:/Windows/Fonts/malgun.ttf",
                "C:/Windows/Fonts/malgungbd.ttf",
            ]
        else:
            candidates = [
                "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
                "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            ]

        font_path = None
        for p in candidates:
            if os.path.exists(p):
                font_path = p
                break

        if font_path:
            return {
                "title": ImageFont.truetype(font_path, 28),
                "heading": ImageFont.truetype(font_path, 16),
                "body": ImageFont.truetype(font_path, 13),
                "small": ImageFont.truetype(font_path, 11),
                "mono": ImageFont.truetype(font_path, 10),
            }

        logger.warning("No suitable font found — CJK may break.")
        default = ImageFont.load_default()
        return {k: default for k in ("title", "heading", "body", "small", "mono")}

    # ── 내부: 카드 이미지 렌더링 ──
    def _draw_card(self, data: dict) -> Image.Image:
        """분석 결과(data)를 시각화한 800×480 Knowledge-Graph 카드 이미지를 반환."""
        W, H = self._CARD_SIZE
        img = Image.new("RGB", (W, H), color=(15, 15, 35))
        draw = ImageDraw.Draw(img)
        fonts = self._load_fonts()

        # ── 배경 그리드 (그래프 느낌) ──
        grid_color = (96, 165, 250, 8)
        for x in range(0, W, 32):
            draw.line([(x, 0), (x, H)], fill=grid_color, width=1)
        for y in range(0, H, 32):
            draw.line([(0, y), (W, y)], fill=grid_color, width=1)

        # ── 상단 악센트 라인 ──
        draw.rectangle([(0, 0), (W, 3)], fill=(96, 165, 250))

        # ── 타이틀 ──
        topics = data.get("topics", [])
        title_text = topics[0]["title"] if topics else "SpeakNode Summary"
        draw.text((30, 18), title_text, fill=(229, 231, 235), font=fonts["title"])

        # ── 브랜딩 ──
        draw.text((W - 130, 14), "SpeakNode", fill=(96, 165, 250), font=fonts["heading"])
        draw.text((W - 160, 34), "Knowledge Graph", fill=(75, 85, 99), font=fonts["small"])

        # ── Stats 뱃지 ──
        bx, by = 30, 68
        for label, key, color in self._BADGE_DEFS:
            count = len(data.get(key, []))
            if count == 0:
                continue
            text = f"{label} {count}"
            tw = draw.textlength(text, font=fonts["small"]) + 20
            draw.rounded_rectangle(
                [(bx, by), (bx + tw, by + 20)], radius=4,
                fill=(*color, 30), outline=(*color, 80),
            )
            draw.ellipse([(bx + 6, by + 6), (bx + 13, by + 13)], fill=color)
            draw.text((bx + 17, by + 3), text, fill=(209, 213, 219), font=fonts["small"])
            bx += tw + 10

        # ── 구분선 ──
        draw.line([(30, 100), (W - 30, 100)], fill=(255, 255, 255, 15), width=1)

        # ── Topics 섹션 ──
        y = 115
        draw.text((30, y), "Topics", fill=(34, 197, 94), font=fonts["heading"])
        y += 24
        for t in (topics or [])[:3]:
            draw.ellipse([(36, y + 4), (42, y + 10)], fill=(34, 197, 94))
            draw.text((50, y), t.get("title", ""), fill=(229, 231, 235), font=fonts["body"])
            y += 18
            summary = t.get("summary", "")
            if summary:
                for line in textwrap.wrap(summary, width=60)[:2]:
                    draw.text((50, y), line, fill=(107, 114, 128), font=fonts["small"])
                    y += 15
            y += 6

        # ── Tasks 섹션 ──
        tasks = data.get("tasks", [])
        if y < H - 120 and tasks:
            y += 4
            draw.text((30, y), "Tasks", fill=(245, 158, 11), font=fonts["heading"])
            y += 24
            for t in tasks[:4]:
                if y > H - 60:
                    break
                sc = self._STATUS_COLORS.get(t.get("status", "pending"), (245, 158, 11))
                draw.ellipse([(36, y + 4), (42, y + 10)], fill=sc)
                task_text = f"{t.get('description', '')}  →  {t.get('assignee', '?')}"
                draw.text((50, y), task_text, fill=(209, 213, 219), font=fonts["small"])
                y += 18

        # ── 하단 브랜딩 바 ──
        draw.rectangle([(0, H - 32), (W, H)], fill=(0, 0, 0, 100))
        draw.text(
            (12, H - 24),
            "speaknode_graph_bundle_v1  |  embedded JSON data",
            fill=(75, 85, 99),
            font=fonts["mono"],
        )

        return img

    # ── 공개 API ──
    def create_card(
        self,
        data: dict,
        filename: str = "meeting_card.png",
        *,
        payload: dict | None = None,
    ) -> str:
        """Generate a Knowledge-Graph summary card with data embedded in PNG metadata.

        Args:
            data: 분석 결과 dict (topics, tasks 등). 카드 비주얼 렌더링에 사용.
            filename: 저장할 파일 이름.
            payload: PNG 메타데이터에 임베딩할 dict.
                     주어지지 않으면 *data* 자체를 임베딩한다 (하위호환).
        """
        safe_filename = os.path.basename(filename) or "meeting_card.png"

        # 카드 이미지 렌더링
        img = self._draw_card(data)

        # 메타데이터 임베딩: payload가 있으면 payload를, 없으면 data를
        embed_data = payload if payload is not None else data
        metadata = PngInfo()
        metadata.add_text("speaknode_data_zlib_b64", self._encode_payload(embed_data))

        # 저장
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
