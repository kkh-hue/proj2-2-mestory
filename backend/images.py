"""채팅 말풍선에 다시 그릴 용도로 첨부 사진을 작게 줄인다 (docs/specs/chat-image-persistence.md).

왜 줄이나:
    백엔드는 1장 5MB까지 받는데(main.py MAX_IMAGE_BYTES), base64로 바꾸면 약 1.33배가 되어
    6.7MB다. 3장이면 한 턴에 20MB. list_chat_turns()는 세션의 모든 턴을 한 번에 돌려주므로
    사진이 몇 턴만 쌓여도 응답이 수십 MB가 되어 화면이 멈춘다.
    말풍선에 보이는 건 작은 썸네일이라 원본 해상도가 필요 없다.

무엇을 줄이지 않나:
    **LLM에 보내는 이미지는 원본 그대로다.** 거기서 줄이면 이미지에서 글자를 읽어내는
    정확도(visual_extraction)가 떨어진다. 줄이는 것은 DB에 남기는 사본뿐이다.
"""

from __future__ import annotations

import base64
import binascii
import io
import logging
import re

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

# 가로·세로 중 긴 쪽을 이 픽셀에 맞춘다(비율 유지). 말풍선 썸네일은 이 정도면 충분하다.
THUMBNAIL_MAX_PX = 512
# JPEG 품질. 70이면 눈으로 보기에 무리 없으면서 용량이 크게 준다.
THUMBNAIL_QUALITY = 70

# "data:image/png;base64,iVBOR..." 를 (형식, 내용) 두 조각으로 나눈다 (main.py와 같은 모양).
_DATA_URL_RE = re.compile(r"^data:image/([A-Za-z0-9.+\-]+);base64,(.+)$", re.DOTALL)


def to_thumbnail(data_url: str) -> str | None:
    """data URL 한 장을 작은 JPEG data URL로 바꾼다. 못 바꾸면 None.

    예외를 올리지 않는 이유: 사진 한 장이 깨졌다고 리포트 생성 전체가 실패하면 안 된다.
    저장은 부가 기능이고, 분석 결과를 돌려주는 것이 본래 목적이다.
    """
    match = _DATA_URL_RE.match(data_url or "")
    if not match:
        logger.warning("썸네일 변환 건너뜀 — data URL 형식이 아닙니다")
        return None

    try:
        raw = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError) as exc:
        logger.warning("썸네일 변환 건너뜀 — base64를 풀지 못했습니다: %s", exc)
        return None

    try:
        with Image.open(io.BytesIO(raw)) as image:
            # 휴대폰 사진은 회전 정보가 EXIF에만 들어 있다. 이걸 먼저 적용하지 않으면
            # 줄이는 순간 방향 정보가 사라져 옆으로 누운 썸네일이 된다.
            image = ImageOps.exif_transpose(image)

            # JPEG는 투명도를 담지 못한다. 알파가 있으면 흰 배경에 합성한 뒤 RGB로 바꾼다.
            if image.mode in ("RGBA", "LA", "P"):
                image = image.convert("RGBA")
                canvas = Image.new("RGB", image.size, (255, 255, 255))
                canvas.paste(image, mask=image.split()[-1])
                image = canvas
            elif image.mode != "RGB":
                image = image.convert("RGB")

            # thumbnail()은 원본이 이미 작으면 확대하지 않는다 — 작은 사진은 그대로 둔다.
            image.thumbnail((THUMBNAIL_MAX_PX, THUMBNAIL_MAX_PX))

            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=THUMBNAIL_QUALITY, optimize=True)
    except Exception as exc:  # PIL은 깨진 파일에 대해 여러 종류의 예외를 낸다
        logger.warning("썸네일 변환 건너뜀 — 이미지를 열지 못했습니다: %s", exc)
        return None

    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def to_thumbnails(data_urls: list[str] | None) -> list[str]:
    """여러 장을 줄인다. 변환에 실패한 장은 조용히 빼고 나머지만 돌려준다."""
    if not data_urls:
        return []
    thumbnails = [to_thumbnail(url) for url in data_urls]
    kept = [thumb for thumb in thumbnails if thumb]
    if len(kept) < len(thumbnails):
        logger.warning("첨부 사진 %d장 중 %d장만 저장합니다", len(thumbnails), len(kept))
    return kept
