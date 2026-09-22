"""멀티모달 입력 AC — docs/specs/multimodal.md

실제 LLM/MCP 호출 없이 확인할 수 있는 AC만 여기에 담았다.
가짜 LLM(FakeToolCallingLLM)을 써서 "모델이 실제로 받은 메시지"까지 들여다본다.

여기서 확인하지 않는 AC (실제 API 키가 필요해서 `실습/try_multimodal.py`로 확인):
  AC-05 이미지가 근거에 반영된다
  AC-06 이미지를 빼면 달라진다 (기여 증명)
  AC-07 읽을 수 없는 이미지는 추측하지 않는다
  AC-08 이미지 속 설비ID가 입력과 다를 때
"""

import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool

from backend.services import llm as llm_module

# 이 파일의 시험은 CSV/DB 데이터가 없어도 돌아간다 (conftest.py의 no_data 표시).
pytestmark = pytest.mark.no_data


# ─────────────────────────────────────────────
# 준비물
# ─────────────────────────────────────────────
# 실제 이미지 대신 쓰는 짧은 data URL. 정규식이 잡을 만큼(40자 이상) 길게 둔다.
FAKE_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
FAKE_IMAGE = f"data:image/png;base64,{FAKE_BASE64}"


@tool
def get_downtime_logs(equipment_id: str) -> str:
    """설비의 정지 로그를 조회한다."""
    return '{"record_count": 1}'


TOOLS = [get_downtime_logs]


class FakeToolCallingLLM(GenericFakeChatModel):
    """도구 호출을 흉내 내는 가짜 모델.

    왜 필요한가: 프롬프트가 잘 만들어지는 것과, 에이전트를 끝까지 돌렸을 때
    모델이 이미지를 받는 것은 별개다. 실제 모델을 부르지 않고 그 사이를 확인하려면
    "받은 메시지를 기록해 두는 가짜 모델"이 필요하다.
    """

    seen_messages: list = []

    def bind_tools(self, tools, **kwargs):  # 에이전트가 만들어지려면 이게 있어야 한다
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        FakeToolCallingLLM.seen_messages = list(messages)
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def _fake_llm() -> FakeToolCallingLLM:
    return FakeToolCallingLLM(messages=iter([AIMessage(content='{"ok": true}')] * 10))


def _prompt(style: str) -> ChatPromptTemplate:
    """style="now" = 고치기 전 코드, style="fix" = 고친 코드."""
    human_part = ("human", "{input}") if style == "now" else MessagesPlaceholder("input")
    return ChatPromptTemplate.from_messages([
        ("system", "너는 설비 분석 에이전트다."),
        MessagesPlaceholder("chat_history", optional=True),
        human_part,
        MessagesPlaceholder("agent_scratchpad"),
    ])


def _has_image(content) -> bool:
    return isinstance(content, list) and any(
        isinstance(part, dict) and part.get("type") == "image_url" for part in content
    )


@pytest.fixture
def api(monkeypatch):
    """backend/main.py를 따로 불러와, generate_report를 가짜로 바꿔 둔다.
    (tests/test_report_api.py와 같은 방식 — 다른 시험의 앱·환경을 건드리지 않으려고.)"""
    path = Path(__file__).resolve().parents[1] / "backend" / "main.py"
    spec = importlib.util.spec_from_file_location("backend._multimodal_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    generator = AsyncMock(side_effect=AssertionError("LLM 호출은 모의 처리해야 합니다"))
    monkeypatch.setattr(module, "generate_report", generator)
    monkeypatch.setattr(module, "get_model_name", lambda: "test-model")
    return module, generator


# ─────────────────────────────────────────────
# AC-01 · 이미지가 프롬프트를 통과한다
# ─────────────────────────────────────────────
def test_AC01_이미지가_프롬프트를_통과한다():
    rendered = _prompt("fix").invoke({
        "input": [HumanMessage(content=[
            {"type": "text", "text": "이 화면 분석해줘"},
            {"type": "image_url", "image_url": {"url": FAKE_IMAGE}},
        ])],
        "agent_scratchpad": [],
    })
    human = [m for m in rendered.to_messages() if isinstance(m, HumanMessage)][0]
    assert isinstance(human.content, list)
    assert _has_image(human.content)


# ─────────────────────────────────────────────
# AC-02 · 고치기 전 코드로는 이미지가 사라진다 (회귀 방지용 반례)
#   이 시험이 실패하면 = 누군가 ("human","{input}")으로 되돌렸는데도
#   이미지가 살아남는다는 뜻이므로, 그때 이 시험을 지워도 된다.
# ─────────────────────────────────────────────
def test_AC02_옛_방식은_이미지를_글자로_바꾼다():
    rendered = _prompt("now").invoke({
        "input": [
            {"type": "text", "text": "이 화면 분석해줘"},
            {"type": "image_url", "image_url": {"url": FAKE_IMAGE}},
        ],
        "agent_scratchpad": [],
    })
    human = [m for m in rendered.to_messages() if isinstance(m, HumanMessage)][0]
    assert isinstance(human.content, str)      # 리스트가 글자로 변환됨
    assert not _has_image(human.content)       # 이미지 소실


# ─────────────────────────────────────────────
# AC-03 · 에이전트 파이프라인 끝까지 이미지가 남는다
# ─────────────────────────────────────────────
def test_AC03_에이전트를_돌린_뒤에도_이미지가_남는다():
    agent = create_tool_calling_agent(_fake_llm(), TOOLS, _prompt("fix"))
    executor = AgentExecutor(agent=agent, tools=TOOLS, handle_parsing_errors=True)
    executor.invoke({
        "input": [HumanMessage(content=[
            {"type": "text", "text": "이 화면 분석해줘"},
            {"type": "image_url", "image_url": {"url": FAKE_IMAGE}},
        ])],
        "chat_history": [],
    })
    human = [m for m in FakeToolCallingLLM.seen_messages if isinstance(m, HumanMessage)][0]
    assert _has_image(human.content)


# ─────────────────────────────────────────────
# AC-04 · 이미지 없는 요청 회귀 없음
#   프롬프트 텍스트가 예전과 한 글자도 다르지 않아야 한다.
# ─────────────────────────────────────────────
def test_AC04_이미지가_없으면_옛_프롬프트와_같다():
    messages, history_text = llm_module._build_user_messages(
        period="2026-08-10 ~ 2026-08-10",
        line_label="LINE-A",
        equipment_label="EQ-001",
        images=None,
    )
    expected = (
        "아래 조건에 해당하는 정지 기록을 MCP 도구로 조회하고, 원인 분석 리포트를 생성해줘.\n"
        "- 기간: 2026-08-10 ~ 2026-08-10\n- 라인: LINE-A\n- 설비: EQ-001"
    )
    assert len(messages) == 1
    assert messages[0].content == expected   # 문자열 그대로 (리스트가 아니다)
    assert history_text == expected
    assert "첨부 이미지" not in messages[0].content


@pytest.mark.parametrize("empty", [None, []])
def test_AC04_빈_이미지_목록도_이미지_없음과_같다(empty):
    messages, _ = llm_module._build_user_messages(
        period="전체 ~ 전체", line_label="전체 라인",
        equipment_label="전체 설비", images=empty,
    )
    assert isinstance(messages[0].content, str)


def test_AC04_이미지가_있으면_리스트가_되고_지시문이_붙는다():
    messages, history_text = llm_module._build_user_messages(
        period="2026-08-10 ~ 2026-08-10", line_label="LINE-A",
        equipment_label="EQ-001", images=[FAKE_IMAGE, FAKE_IMAGE],
    )
    content = messages[0].content
    assert isinstance(content, list)
    assert content[0]["type"] == "text"
    assert "첨부 이미지 2장" in content[0]["text"]
    assert "추측해서 채우지 마라" in content[0]["text"]
    # 이미지 조각이 2개
    assert sum(1 for part in content if part.get("type") == "image_url") == 2
    # 기록용 텍스트에는 base64가 없다 (AC-10과 이어진다)
    assert FAKE_BASE64 not in history_text


# ─────────────────────────────────────────────
# AC-09 · 잘못된 이미지 입력은 422, 서버는 계속 동작
# ─────────────────────────────────────────────
@pytest.mark.parametrize("images,keyword", [
    (["not-a-data-url"], "data URL"),
    ([f"data:image/gif;base64,{FAKE_BASE64}"], "지원하지 않습니다"),
    ([FAKE_IMAGE] * 4, "최대 3장"),
])
def test_AC09_잘못된_이미지는_422(api, images, keyword):
    module, generator = api
    with TestClient(module.app) as client:
        response = client.post("/report", json={"images": images})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "images"]
    assert keyword in response.json()["detail"][0]["msg"]
    generator.assert_not_awaited()          # LLM까지 가지 않았다


def test_AC09_용량_초과는_422(api):
    module, generator = api
    # base64 글자 4개 = 원본 3바이트 → 6MB를 넘기려면 8MB 남짓의 글자가 필요하다
    huge = "data:image/png;base64," + ("A" * (8 * 1024 * 1024))
    with TestClient(module.app) as client:
        response = client.post("/report", json={"images": [huge]})
    assert response.status_code == 422
    assert "너무 큽니다" in response.json()["detail"][0]["msg"]
    generator.assert_not_awaited()


def test_AC09_422가_나도_서버는_계속_동작한다(api):
    module, generator = api
    with TestClient(module.app) as client:
        assert client.post("/report", json={"images": ["bad"]}).status_code == 422
        assert client.get("/health").json() == {"status": "ok"}   # 서버 살아있음


# ─────────────────────────────────────────────
# AC-10 · base64가 기록·트레이스에 남지 않는다
# ─────────────────────────────────────────────
def test_AC10_마스킹이_base64를_잘라낸다():
    masked = llm_module._mask_base64(data=f"화면: {FAKE_IMAGE} 끝")
    assert FAKE_BASE64 not in masked
    assert "data:image/png;base64," in masked   # 앞머리는 남겨 무엇이 있었는지 알 수 있게
    assert "자 생략" in masked


def test_AC10_마스킹이_중첩된_구조도_훑는다():
    """Langfuse가 넘기는 입력은 문자열이 아니라 메시지 목록 안의 dict다."""
    data = {"messages": [[{"content": [
        {"type": "text", "text": "분석해줘"},
        {"type": "image_url", "image_url": {"url": FAKE_IMAGE}},
    ]}]]}
    masked = llm_module._mask_base64(data=data)
    assert FAKE_BASE64 not in repr(masked)
    assert masked["messages"][0][0]["content"][0]["text"] == "분석해줘"  # 텍스트는 보존


def test_AC10_마스킹은_일반_텍스트를_건드리지_않는다():
    plain = "EQ-001 설비가 41.9분 정지했습니다."
    assert llm_module._mask_base64(data=plain) == plain
    assert llm_module._mask_base64(data=42) == 42
    assert llm_module._mask_base64(data=None) is None


# Langfuse는 '공개키당 설정 저장소 하나'라는 프로세스 전역 싱글턴을 쓴다.
# 이 시험에서 클라이언트를 만들면 다른 시험까지 오염되므로, 별도 프로세스로 돌린다.
_LANGFUSE_WIRING_SCRIPT = """
import os, sys
os.environ.update({
    "LANGFUSE_PUBLIC_KEY": "pk-lf-test", "LANGFUSE_SECRET_KEY": "sk-lf-test",
    "LANGFUSE_HOST": "http://localhost:3000",
})
sys.path.insert(0, "__REPO__")
if __PREINIT__:
    # 다른 코드가 우리보다 먼저 클라이언트를 만든 상황을 재현한다.
    from langfuse import Langfuse
    Langfuse()
from backend.services import llm as m
from langfuse import get_client
handler = m._build_run_config("s", None, None)["callbacks"][0]
ok = (getattr(handler._langfuse_client, "_mask", None) is m._mask_base64
      and getattr(get_client(), "_mask", None) is m._mask_base64)
print("APPLIED" if ok else "NOT_APPLIED")
"""


@pytest.mark.parametrize("preinit", [False, True], ids=["우리가_먼저", "남이_먼저"])
def test_AC10_마스킹이_Langfuse에_실제로_연결된다(preinit):
    """마스킹 함수가 잘 동작하는 것과, Langfuse가 그걸 실제로 쓰는 것은 별개다.

    특히 preinit=True(남이 먼저 클라이언트를 만든 경우)는 Langfuse의 설정 저장소가
    싱글턴이라 `Langfuse(mask=...)`가 조용히 무시되는 경로다. llm.py의
    _ensure_langfuse_mask가 그걸 감지해 직접 꽂아 넣는지 확인한다.
    """
    import subprocess
    import sys

    repo = str(Path(__file__).resolve().parents[1])
    # .format()을 쓰면 스크립트 안의 { } 를 변수 자리로 읽어 버린다 (llm.py의
    # _escape_braces가 있는 이유와 같은 함정). 그래서 단순 치환을 쓴다.
    script = (_LANGFUSE_WIRING_SCRIPT
              .replace("__REPO__", repo.replace("\\", "\\\\"))
              .replace("__PREINIT__", str(bool(preinit))))
    done = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=120,
    )
    assert "APPLIED" in done.stdout, (
        f"마스킹이 Langfuse에 연결되지 않았습니다.\nstdout={done.stdout}\nstderr={done.stderr[-2000:]}"
    )


def test_AC10_기록용_텍스트에는_base64가_없다():
    _, history_text = llm_module._build_user_messages(
        period="전체 ~ 전체", line_label="LINE-A",
        equipment_label="EQ-001", images=[FAKE_IMAGE],
    )
    assert "data:image" not in history_text
    assert FAKE_BASE64 not in history_text


# ─────────────────────────────────────────────
# AC-11 · /api/agent 경로 (가이드 6쪽 공통 포맷)
# ─────────────────────────────────────────────
@pytest.mark.parametrize("path", ["/report", "/api/agent"])
def test_AC11_두_경로가_같은_응답을_준다(api, path):
    module, generator = api
    expected = {
        "equipment_id": "EQ-001", "line_id": "LINE-A", "period": "2026-08-10 ~ 2026-08-10",
        "causes": [], "unclassified_count": 0,
        "confidence_note": "시험 응답", "recommended_action": "확인 필요",
        "visual_findings": None, "used_image": False,
    }
    generator.side_effect = None
    generator.return_value = module.DowntimeReport(**expected)
    with TestClient(module.app) as client:
        response = client.post(path, json={"line_id": "LINE-A"})
    assert response.status_code == 200
    assert response.json() == expected


def test_AC11_이미지를_보내면_그대로_전달된다(api):
    """라우터는 검증만 하고 generate_report로 넘긴다 (이미지를 해석하지 않는다).

    line_id가 LINE-A인 이유: resolve_scope()(backend/scope.py)가 설비ID로 설비
    마스터를 조회해 라인을 채운다. 라우터가 이미지를 해석한 결과가 아니라
    마스터 조회 결과이므로, 이 시험의 취지(라우터는 해석하지 않는다)는 유지된다.
    """
    module, generator = api
    generator.side_effect = None
    generator.return_value = module.DowntimeReport(
        equipment_id="EQ-001", line_id="LINE-A", period="전체 ~ 전체",
        causes=[], unclassified_count=0,
        confidence_note="", recommended_action="",
        visual_findings=["화면에 M-204 표시됨"], used_image=True,
    )
    with TestClient(module.app) as client:
        response = client.post("/api/agent", json={
            "equipment_id": "EQ-001", "images": [FAKE_IMAGE],
        })
    assert response.status_code == 200
    body = response.json()
    assert body["used_image"] is True
    assert body["visual_findings"] == ["화면에 M-204 표시됨"]
    generator.assert_awaited_once()
    call_kwargs = dict(generator.call_args.kwargs)
    call_kwargs.pop("report_id")  # 요청마다 새로 만드는 UUID — 값 자체는 다른 시험에서 확인
    # user_id는 서버가 정하는 요청 출처 라벨이라 요청 본문과 무관하다 (docs/specs/langfuse-user-id.md).
    assert call_kwargs.pop("user_id") == "web"
    assert call_kwargs == {
        "line_id": "LINE-A", "equipment_id": "EQ-001", "date_from": None, "date_to": None,
        "session_id": None, "images": [FAKE_IMAGE], "message": None,
    }
