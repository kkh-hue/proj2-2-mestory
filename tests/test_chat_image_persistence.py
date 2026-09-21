"""채팅 첨부 사진 유지 AC — docs/specs/chat-image-persistence.md

핵심은 "화면에는 다시 보이되, LLM 대화 맥락에는 절대 들어가지 않는다"이다.
AC-01(새로고침 후 화면 표시)은 프론트 테스트 러너가 없어 수동으로 확인한다.
"""

import asyncio
import base64
import io
import json

import pytest
from PIL import Image

from backend import db
from backend.images import to_thumbnail, to_thumbnails

# 이 파일의 시험은 CSV/DB 데이터가 없어도 돌아간다 (conftest.py의 no_data 표시).
pytestmark = pytest.mark.no_data


def make_data_url(width: int = 1600, height: int = 1200, mode: str = "RGB") -> str:
    """시험용 이미지 한 장을 data URL로 만든다."""
    image = Image.new(mode, (width, height), (90, 120, 200) if mode == "RGB" else (90, 120, 200, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


class RecordingConnection:
    """execute로 들어온 SQL과 파라미터를 그대로 모아 두는 가짜 연결."""

    def __init__(self, rows=None):
        self.calls = []
        self._rows = rows or []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def execute(self, *args):
        self.calls.append(args)
        return self

    async def fetchall(self):
        return self._rows


def connect_returning(connection):
    async def _connect():
        return connection
    return _connect


# ─────────────────────────────────────────────
# AC-02 · LLM 맥락에는 이미지가 들어가지 않는다 (multimodal.md AC-10 유지)
# ─────────────────────────────────────────────
def test_AC02_저장할_때_content에는_이미지가_없다(monkeypatch):
    connection = RecordingConnection()
    monkeypatch.setattr(db, "_connect", connect_returning(connection))

    asyncio.run(db.save_message(
        "session-1", "user", "기간: 전체 · 라인: LINE-A",
        display_content="사진 보고 분석해줘", images=[make_data_url()],
    ))

    params = connection.calls[0][1]
    content = params[2]                       # insert 컬럼 순서: session_id, role, content, ...
    assert "data:image" not in content        # ← AC-10의 핵심
    assert params[5] is not None              # display_images에는 들어갔다


def test_AC02_load_chat_history_결과에_data_image가_없다(monkeypatch):
    # DB에는 이미지가 저장돼 있어도, LLM 맥락을 만드는 이 함수는 content만 읽는다.
    rows = [("user", "기간: 전체 · 라인: LINE-A"), ("assistant", '{"equipment_id": "EQ-001"}')]
    connection = RecordingConnection(rows)
    monkeypatch.setattr(db, "_connect", connect_returning(connection))

    messages = asyncio.run(db.load_chat_history("session-1"))

    assert messages, "대화 기록이 비어 있으면 시험의 의미가 없다"
    for message in messages:
        assert "data:image" not in str(message.content)

    # select 문이 display_images를 아예 읽지 않는지도 확인한다 —
    # 나중에 누가 컬럼을 추가해도 이 경로로는 새어 나가지 않아야 한다.
    sql = connection.calls[0][0]
    assert "display_images" not in sql


# ─────────────────────────────────────────────
# AC-03 · 저장되는 이미지가 충분히 작다
# ─────────────────────────────────────────────
def test_AC03_썸네일이_200KB_이하이고_유효한_data_url이다():
    original = make_data_url(4000, 3000)
    thumbnail = to_thumbnail(original)

    assert thumbnail is not None
    assert thumbnail.startswith("data:image/")
    assert len(thumbnail) < len(original)
    assert len(thumbnail) / 1024 <= 200

    # 실제로 열리는 이미지인지 — 형식만 맞고 내용이 깨졌으면 화면에서 깨져 보인다
    payload = base64.b64decode(thumbnail.split(",", 1)[1])
    with Image.open(io.BytesIO(payload)) as reopened:
        assert max(reopened.size) <= 512


def test_AC03_작은_이미지는_확대하지_않는다():
    original = make_data_url(120, 90)
    payload = base64.b64decode(to_thumbnail(original).split(",", 1)[1])
    with Image.open(io.BytesIO(payload)) as reopened:
        assert reopened.size == (120, 90)


def test_AC03_투명한_PNG도_변환된다():
    # JPEG는 알파를 못 담는다 — 흰 배경에 합성해야 하며, 예외가 나면 안 된다
    assert to_thumbnail(make_data_url(800, 600, mode="RGBA")) is not None


# ─────────────────────────────────────────────
# AC-04 · 변환 실패가 리포트 생성을 막지 않는다
# ─────────────────────────────────────────────
@pytest.mark.parametrize("broken", [
    "data:image/png;base64,이건base64가아니다",
    "data:image/png;base64,QUJD",          # 풀리지만 이미지가 아님
    "그냥 텍스트",
    "",
])
def test_AC04_깨진_이미지는_None을_돌려준다(broken):
    assert to_thumbnail(broken) is None


def test_AC04_깨진_것이_섞여도_정상인_것만_남는다():
    kept = to_thumbnails(["data:image/png;base64,망가짐", make_data_url(400, 300)])
    assert len(kept) == 1
    assert kept[0].startswith("data:image/")


def test_AC04_빈_입력은_빈_목록이다():
    assert to_thumbnails(None) == []
    assert to_thumbnails([]) == []


# ─────────────────────────────────────────────
# AC-05 · 이미지 없는 요청에 회귀가 없다
# ─────────────────────────────────────────────
def test_AC05_images를_안_주면_display_images가_NULL이다(monkeypatch):
    connection = RecordingConnection()
    monkeypatch.setattr(db, "_connect", connect_returning(connection))

    # 기존 호출부와 똑같은 형태 (images 인자 없음)
    asyncio.run(db.save_message("session-1", "assistant", "본문", report_id="report-1"))

    assert connection.calls[0][1][5] is None


# ─────────────────────────────────────────────
# AC-06 · 옛 대화(display_images가 NULL)도 깨지지 않는다
# ─────────────────────────────────────────────
def _turn_row(display_images):
    from datetime import datetime
    return (
        "user", "content", "화면용 문장", None, datetime(2026, 9, 21, 10, 0), display_images,
        None, None, None, None, None, None, None, None, None, None,
    )


def test_AC06_display_images가_NULL이면_images_키가_없다(monkeypatch):
    connection = RecordingConnection([_turn_row(None)])
    monkeypatch.setattr(db, "_connect", connect_returning(connection))

    turns = asyncio.run(db.list_chat_turns("session-1"))

    assert turns[0]["content"] == "화면용 문장"
    assert "images" not in turns[0]


def test_AC06_display_images가_있으면_그대로_돌려준다(monkeypatch):
    saved = ["data:image/jpeg;base64,AAAA"]
    connection = RecordingConnection([_turn_row(saved)])
    monkeypatch.setattr(db, "_connect", connect_returning(connection))

    turns = asyncio.run(db.list_chat_turns("session-1"))

    assert turns[0]["images"] == saved
