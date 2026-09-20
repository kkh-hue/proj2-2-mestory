"""LLM 호출은 이 파일 하나로 모읍니다.

라우터나 UI 코드가 openai를 직접 import하지 않게 하세요.
3차에서 이 파일 내부만 갈아끼우면 나머지는 그대로 돌아갑니다.

여기서 책임지는 것:
  - LangChain 도구 호출 에이전트(create_tool_calling_agent + AgentExecutor)로
    mcp_server가 제공하는 MCP 도구를 불러와 정지 로그/에러코드 사전/정비이력을 조회하고 리포트 생성
  - 출력 계약 검증 (Pydantic: DowntimeReport, DowntimeCause) — PRD 5-2
  - 실패 시 3단계 재시도 후 명시적 분석 예외 전달
  - Langfuse 트레이스 남기기 (입력/출력/지연시간/토큰 사용량)
  - SKILL.md의 판단 규칙을 시스템 프롬프트로 주입

LangGraph는 이 프로젝트에서 금지되어 있어 사용하지 않는다 (docs/MESTORY_기능목록.md 범위 밖 참고).
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Literal

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_openai import ChatOpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import get_default_environment, stdio_client
from pydantic import BaseModel, Field, ValidationError

from ..db import load_chat_history, save_message, save_report

try:
    # langfuse>=3부터 CallbackHandler가 langfuse.callback → langfuse.langchain으로 옮겨졌고
    # (langfuse.callback 모듈 자체가 없어짐), session_id/trace_name/metadata를 생성자가 아니라
    # LangChain invoke config의 metadata(langfuse_* 키)로 받는 방식으로 바뀌었다.
    from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler
except ImportError:  # langfuse가 아직 설치 안 됐을 때도 서비스는 뜨게
    LangfuseCallbackHandler = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

# backend/services/llm.py 기준 저장소 최상위 폴더
REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = REPO_ROOT / "skills" / "SKILL.md"

# mcp_server/server.py를 `python -m mcp_server.server`로 서브프로세스로 띄워 stdio로 연결한다.
# (server.py를 파일 경로로 직접 실행하면, 이후 팀원이 안에서 `from .tools...`처럼
#  상대 import를 쓰는 순간 "attempted relative import" 에러가 나기 때문에 -m 방식을 쓴다.)
MCP_SERVER_MODULE = "mcp_server.server"

# MCP SDK는 보안상 서브프로세스에 PATH 등 최소 환경변수만 기본으로 물려준다
# (mcp.client.stdio.get_default_environment). data_loader.py가 DB 모드로
# 동작하려면 DATABASE_URL 등을 명시적으로 넘겨야 한다 — 안 넘기면 항상 csv 모드로
# 동작하는데, 배포 환경엔 CSV가 없어서 결국 실패한다.
MCP_ENV_PASSTHROUGH = (
    "MESTORY_DATA_SOURCE",
    "MESTORY_DATA_DIR",
    "DATABASE_URL",
    "DATABASE_PUBLIC_URL",
)

AGENT_MAX_ITERATIONS = 8  # 도구 호출 무한루프 방지용 상한

# 출력 토큰 상한.
# 왜 굳이 거는가 (여기서 한 번 막혔다):
#   OpenRouter는 요청마다 '최대로 나올 수 있는 비용'을 잔액에서 미리 잡아둔다.
#   그 계산이 (입력 토큰 + max_tokens만큼의 출력 토큰)인데, max_tokens를 주지 않으면
#   모델의 출력 상한(gpt-4o-mini는 16k)으로 잡는다. 우리 리포트 JSON은 1000토큰도
#   안 나오므로 10배 넘게 과하게 잡히고, 잔액이 빠듯하면 몇 건 만에
#   402 in_flight_budget_exhausted 로 막힌다.
#   값을 더 줄이면 잔액은 아끼지만 긴 리포트가 잘려 JSON 파싱이 깨진다.
#   causes가 여러 건인 최악의 경우를 재보고 여유를 둔 값이 2000이다.
#   ⚠️ 추론 모델(gpt-5 계열)로 바꾸면서 같은 예산 안에서 추론 토큰까지 나눠 쓰게 됐다.
#      2000으로는 부족해 리포트 JSON이 중간에 잘렸다(실측: 2,363자·2,905자 지점에서 절단).
MAX_OUTPUT_TOKENS = 4000

# 이미지는 "data:image/png;base64,iVBOR..." 같은 data URL 한 줄로 들어온다.
# 이 정규식은 앞머리(data:image/png;base64,)와 뒤의 긴 base64 덩어리를 따로 잡는다.
# 왜 필요한가: 그 덩어리가 Langfuse 트레이스나 대화 기록에 그대로 들어가면
#   ① 트레이스를 사람이 읽을 수 없고 ② 다음 요청마다 통째로 다시 전송돼 비용이 튄다.
_BASE64_IMAGE_RE = re.compile(r"(data:image/[A-Za-z0-9.+\-]+;base64,)[A-Za-z0-9+/=\s]{40,}")


# ─────────────────────────────────────────────
# 출력 계약 (PRD 5-2, 필수 조건 3)
# ─────────────────────────────────────────────
class DowntimeCause(BaseModel):
    error_code: str = Field(description="원인으로 확정/추정한 에러코드")
    description: str = Field(description="원인에 대한 자연어 설명")
    severity: Literal["경미", "보통", "중대", "판정 불가"] = Field(
    description="심각도. 사전에 없는 코드·데이터 오류 등 근거가 없으면 '판정 불가'"
    )
    evidence: str = Field(
        description="판단 근거 — 참고한 MCP 조회 결과(에러코드 사전/정비이력 등)를 구체적으로 명시"
    )
    is_confirmed: bool = Field(description="확정된 판단이면 true, 잠정/추정 판단이면 false")


class DowntimeReport(BaseModel):
    equipment_id: str
    line_id: str
    period: str
    causes: list[DowntimeCause] = Field(default_factory=list)
    unclassified_count: int = Field(ge=0, description="미등록 코드·데이터 오류 등 판정 불가 건수")
    confidence_note: str = Field(description="경계 케이스/불확실성, 사람 확인 필요 여부 명시")
    recommended_action: str = Field(description="표준 권장 조치 문구 (정비팀/자재팀 등 담당 구분 포함)")
    # ── 멀티모달 (docs/specs/multimodal.md) ──
    # 이미지에서 "읽어낸 사실"만 여기에 적는다. 추론·판정은 causes로 간다.
    # 이 칸을 따로 둔 이유: 이미지 근거가 evidence 문장 속에 녹아버리면
    # "이미지가 실제로 쓰였는가"를 채점할 수 없다. 분리해 두면 추출 정확도를 측정할 수 있다.
    visual_findings: list[str] | None = Field(
        default=None,
        description=(
            "첨부 이미지에서 읽어낸 사실 목록. 예: "
            '["화면에 에러코드 M-204 표시됨", "설비 태그 EQ-001 확인", "타임스탬프 2026-08-10 22:14:03"]. '
            "읽을 수 없으면 빈 목록. 이미지에 없는 내용을 추측해서 채우지 마라. 이미지가 없으면 null."
        ),
    )
    # 이 값은 LLM 출력을 믿지 않고 코드가 덮어쓴다 (아래 generate_report 끝부분).
    # 이유: equipment_id/line_id와 같은 원칙 — "사실로 정해진 것은 코드가 정한다".
    used_image: bool = Field(default=False, description="이미지를 근거로 사용했으면 true")


class _SimplifiedReport(BaseModel):
    """2단계 재시도용 축소 스키마. causes 리스트 구조 없이 요약 문장 하나만 요구해서
    복잡한 스키마 때문에 실패했을 가능성을 줄인다."""

    equipment_id: str
    line_id: str
    period: str
    summary: str = Field(description="원인·심각도·근거를 자연어로 요약한 문장")
    unclassified_count: int = Field(ge=0)
    confidence_note: str
    recommended_action: str


# 세션별 대화 기록은 backend/db.py(Postgres)에 저장한다 — 프로세스 메모리가 아니라서
# 재배포·재시작해도 남는다 (F-07). 세션당 보관할 최근 메시지 수(사람+AI 합산).
_SESSION_HISTORY_LIMIT = 10


def _load_skill_text() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def _mcp_subprocess_env() -> dict[str, str]:
    env = get_default_environment()
    for key in MCP_ENV_PASSTHROUGH:
        value = os.getenv(key)
        if value:
            env[key] = value
    return env


def get_model_name() -> str:
    """main.py의 요청 로그에서도 같은 기본값을 쓰도록 노출한다."""
    return os.getenv("MESTORY_LLM_MODEL", "openai/gpt-4o-mini")


# LLM 제공자(provider)를 .env로 갈아끼울 수 있게 해 둔다.
# 기본값은 OpenRouter — 아무것도 설정 안 하면 기존과 똑같이 동작한다.
#
# 왜 이렇게 열어 뒀나:
#   OpenRouter 무료 한도가 바닥나 측정이 멈추는 일을 겪었다(하루 50건).
#   Gemini는 OpenAI 호환 엔드포인트를 제공해서 base_url과 키만 바꾸면
#   같은 ChatOpenAI 코드로 붙는다. 제공자 한 곳에 묶여 있으면
#   그쪽이 막힐 때 할 수 있는 게 없다.
#
# Gemini로 쓸 때 (.env):
#   MESTORY_LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
#   MESTORY_LLM_API_KEY=<Google AI Studio 키>
#   MESTORY_LLM_MODEL=<gemini 모델명>
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


def get_base_url() -> str:
    return os.getenv("MESTORY_LLM_BASE_URL", DEFAULT_BASE_URL)


_tool_call_passthrough_ready = False


def _install_tool_call_passthrough() -> None:
    """도구 호출을 되돌려 보낼 때 제공자가 붙인 추가 필드를 살려 보낸다.

    왜 이런 걸 하나 (Gemini 3.x에서 막혔다):
      Gemini 3.x는 함수 호출 응답에 thought_signature(추론 서명)를 붙이고,
      다음 요청에 그걸 '그대로' 돌려받길 요구한다. 안 주면 400:
        "Function call is missing a thought_signature in functionCall parts"
      그런데 langchain_openai는 내보낼 때 tool_call을 id/type/function 세 칸으로
      새로 만든다(_lc_tool_call_to_openai_tool_call) — 서명이 버려진다.
      받을 때는 additional_kwargs["tool_calls"]에 원본이 남아 있으므로,
      내보내기 직전에 원본의 추가 필드를 id로 짝지어 되붙인다.

      확인 방법: 손으로 조립한 멀티턴 요청(원본 tool_calls를 그대로 전송)은
      통과했고, LangChain 경로만 400이 났다. 차이가 이 필드뿐이었다.

    안전성:
      원본에 있는 필드 중 id/type/function을 덮어쓰지 않고 '없는 것만' 더한다.
      OpenAI처럼 추가 필드가 없는 제공자에서는 더할 게 없어 아무 일도 안 일어난다.

    치우는 방법:
      langchain_openai가 이 필드를 다루게 되면(또는 Gemini를 안 쓰게 되면)
      이 함수와 _build_llm 안의 호출 한 줄만 지우면 된다.
    """
    global _tool_call_passthrough_ready
    if _tool_call_passthrough_ready:
        return
    _tool_call_passthrough_ready = True
    try:
        from langchain_openai.chat_models import base as _oai

        original = _oai._convert_message_to_dict

        def _patched(message):
            result = original(message)
            raw = getattr(message, "additional_kwargs", {}).get("tool_calls")
            if not (result.get("tool_calls") and raw):
                return result
            by_id = {r.get("id"): r for r in raw if isinstance(r, dict)}
            for call in result["tool_calls"]:
                source = by_id.get(call.get("id"))
                if not source:
                    continue
                for key, value in source.items():
                    if key not in call:        # id/type/function은 건드리지 않는다
                        call[key] = value
            return result

        _oai._convert_message_to_dict = _patched
        logger.info("도구 호출의 제공자 추가 필드(thought_signature 등) 전달을 활성화했습니다")
    except Exception as exc:
        # 실패해도 서비스는 떠야 한다. Gemini를 쓸 때만 문제가 되고,
        # 그때는 위의 400 메시지가 그대로 보인다.
        logger.warning("도구 호출 추가 필드 전달 설정 실패: %s", exc)


# ─────────────────────────────────────────────
# OpenRouter에만 붙는 요청 옵션 (다른 provider에는 보내지 않는다)
#
# ① ZDR(Zero Data Retention) — 교육과정 보안 정책이라 반드시 지켜야 한다.
#    계정 설정으로도 걸 수 있지만, 요청에 명시해야 어느 키로 돌려도 보장된다.
#
#    ⚠️ 모델 선택이 여기에 묶인다. tools를 보내면 OpenRouter가
#       'tool calling 되는 엔드포인트'로 한 번 거르고, 그다음 'ZDR 되는 곳'으로
#       또 거른다. openai/gpt-4o-mini는 tools를 지원하는 곳이 OpenAI 하나뿐인데
#       그게 ZDR에서 빠져 두 번째 필터에서 후보가 0이 된다:
#         404 "No endpoints found matching your data policy (Zero data retention)"
#         routing_funnel: 3개 → (tool 호환) 1개 → (data policy) 실패
#       openai/gpt-5-mini는 엔드포인트 4개가 모두 tools를 지원해 ZDR로도 동작한다.
#       모델을 바꿀 때는 scripts/check_zdr.py로 tools+ZDR 조합을 반드시 먼저 확인할 것.
#
# ② reasoning — gpt-5 계열은 추론 토큰을 쓴다. 그냥 두면 그 토큰이
#    max_tokens(=MAX_OUTPUT_TOKENS) 예산을 먼저 써버려 리포트 JSON이 잘린다.
#    Gemini에서 이미 같은 일을 겪었다(답이 빈 문자열이나 'E' 한 글자로 나옴).
#    effort를 낮추고, exclude로 추론 내용 자체는 응답에서 뺀다.
#    MESTORY_LLM_REASONING_EFFORT가 비어 있으면 아예 보내지 않는다(비추론 모델용).
#
# ③ response_format — 모델이 '문법이 깨진 JSON'을 아예 못 내보내게 강제한다.
#    배포본에서 1차·2차 모두 같은 자리에서 깨졌다:
#      JSONDecodeError: Expecting ',' delimiter (line 61 column 6)
#    원인은 모델이 자연어 칸에 큰따옴표를 그대로 쓴 것이다.
#      "코드("MAT-401", "ETC-603")가 많다"   ← 쉼표 앞 따옴표를 닫는 것으로 오해
#    _escape_inner_quotes()가 이 유형을 고치지만, 따옴표 뒤에 쉼표가 오면
#    '진짜 닫는 따옴표'로 판단하도록 돼 있어 이 모양만은 못 고친다.
#    프롬프트로도 안 고쳐진다 — 2차 재시도가 같은 자리에서 또 깨졌다.
#    json_object는 문법만 보장한다. 필드 검증은 기존 Pydantic과 재시도 사다리가 그대로 한다.
#    (엄격한 json_schema는 Pydantic 스키마를 규칙에 맞게 변환해야 해서 지금은 쓰지 않는다)
#    ⚠️ 시스템 프롬프트에 'JSON'이라는 단어가 있어야 동작한다 — _build_prompt가 충족한다.


def _openrouter_extra_body() -> dict | None:
    if "openrouter.ai" not in get_base_url():
        return None

    body: dict = {}
    if os.getenv("MESTORY_LLM_ZDR", "1") != "0":
        body["provider"] = {"zdr": True}

    effort = os.getenv("MESTORY_LLM_REASONING_EFFORT", "").strip()
    if effort:
        body["reasoning"] = {"effort": effort, "exclude": True}

    if os.getenv("MESTORY_LLM_JSON_MODE", "1") != "0":
        body["response_format"] = {"type": "json_object"}
    return body or None


def _build_llm() -> ChatOpenAI:
    # MESTORY_LLM_API_KEY가 있으면 그걸 쓰고, 없으면 기존 OPENROUTER_API_KEY를 쓴다
    # (기존 설정 그대로 두고도 돌아가게).
    _install_tool_call_passthrough()
    api_key = os.getenv("MESTORY_LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "LLM API 키가 없습니다 — MESTORY_LLM_API_KEY 또는 OPENROUTER_API_KEY를 .env에 설정하세요"
        )
    return ChatOpenAI(
        model=get_model_name(),
        api_key=api_key,
        base_url=get_base_url(),
        temperature=0,
        max_tokens=MAX_OUTPUT_TOKENS,
        extra_body=_openrouter_extra_body(),
    )


def _shorten_data_urls(text: str) -> str:
    """문자열 안의 이미지 base64 덩어리를 길이 표시로 바꾼다.
    예: "data:image/png;base64,iVBORw0KGgo..." → "data:image/png;base64,<39264자 생략>"
    """
    def _replace(match: re.Match) -> str:
        head = match.group(1)
        omitted = len(match.group(0)) - len(head)
        return f"{head}<{omitted}자 생략>"

    return _BASE64_IMAGE_RE.sub(_replace, text)


def _mask_base64(*, data: Any) -> Any:
    """Langfuse가 트레이스를 보내기 직전에 부르는 '가리개' 함수.

    Langfuse는 span의 input/output/metadata마다 이 함수를 통과시킨다
    (langfuse/_client/span.py에서 `_mask(data=data)` 형태로 호출).
    입력이 문자열 하나가 아니라 메시지 목록 안에 중첩된 dict일 수 있으므로
    목록·사전을 재귀로 훑어 내려간다. 키워드 인자 이름(data)은 Langfuse가 정한 것이다.
    """
    if isinstance(data, str):
        return _shorten_data_urls(data)
    if isinstance(data, dict):
        return {key: _mask_base64(data=value) for key, value in data.items()}
    if isinstance(data, (list, tuple)):
        return [_mask_base64(data=value) for value in data]
    return data


_langfuse_mask_ready = False


def _ensure_langfuse_mask() -> None:
    """Langfuse에 가리개 함수를 딱 한 번 달고, **정말 달렸는지 확인한다.**

    왜 확인까지 하는가 (여기서 한 번 데였다):
      CallbackHandler는 내부에서 `get_client()`로 '기본 클라이언트'를 찾아 쓴다.
      그런데 Langfuse의 설정 저장소(LangfuseResourceManager)는 공개키당 하나뿐인
      싱글턴이라, **이미 만들어져 있으면 `Langfuse(mask=...)`의 mask가 조용히 무시된다.**
      즉 다른 코드가 우리보다 먼저 클라이언트를 만들면 마스킹이 안 걸리는데
      에러도 경고도 안 난다 — requirements.txt 주석이 경계한 "조용히 꺼짐"과 같은 종류다.

    그래서 ① 정상 경로로 달아보고 ② 확인하고 ③ 안 달렸으면 저장소에 직접 꽂고
    ④ 그래도 안 되면 경고를 남긴다. 경고가 보이면 트레이스에 base64가 남는다는 뜻이다.
    """
    global _langfuse_mask_ready
    if _langfuse_mask_ready:
        return
    _langfuse_mask_ready = True  # 실패해도 매 요청마다 재시도하지 않는다
    try:
        from langfuse import Langfuse, get_client

        # ① 정상 경로 — 아직 클라이언트가 없으면 이것만으로 끝난다
        Langfuse(mask=_mask_base64)

        # ② 확인 (get_client()는 매번 새 껍데기를 주지만 설정 저장소는 공유한다)
        if getattr(get_client(), "_mask", None) is not _mask_base64:
            # ③ 이미 다른 클라이언트가 있었던 경우 — 설정 저장소에 직접 꽂는다
            resources = getattr(get_client(), "_resources", None)
            if resources is not None:
                resources.mask = _mask_base64

        # ④ 최종 확인
        if getattr(get_client(), "_mask", None) is not _mask_base64:
            logger.warning(
                "Langfuse mask가 적용되지 않았습니다 — 트레이스에 이미지 base64가 그대로 남습니다. "
                "다른 코드가 먼저 Langfuse 클라이언트를 만들었거나 langfuse 내부 구조가 바뀐 경우입니다."
            )
    except Exception as exc:  # 키가 없거나 버전이 다를 때도 서비스는 돌아야 한다
        logger.warning(
            "Langfuse mask 설정 실패 — 트레이스에 이미지 base64가 그대로 남을 수 있습니다: %s", exc
        )


def _build_run_config(
    session_id: str | None,
    line_id: str | None,
    equipment_id: str | None,
    user_id: str | None = None,
) -> dict:
    """AgentExecutor.ainvoke(config=...)에 넘길 값. Langfuse 콜백은 이제 생성자가 아니라
    invoke config의 metadata(langfuse_* 키)로 session_id/trace_name을 받는다."""
    if LangfuseCallbackHandler is None or not os.getenv("LANGFUSE_PUBLIC_KEY"):
        return {}
    _ensure_langfuse_mask()  # 핸들러를 만들기 전에 가리개를 먼저 달아 둔다
    metadata = {
        "langfuse_trace_name": "downtime_report",
        "line_id": line_id,
        "equipment_id": equipment_id,
    }
    if session_id:
        metadata["langfuse_session_id"] = session_id
    if user_id:
        # Langfuse Users 화면에서 "누가 만든 요청인가"로 묶인다.
        # 안 붙이면 Users 탭이 통째로 비어 사용자별 사용량·오류를 볼 수 없다.
        metadata["langfuse_user_id"] = user_id
    return {"callbacks": [LangfuseCallbackHandler()], "metadata": metadata}


def _escape_braces(text: str) -> str:
    """ChatPromptTemplate은 기본적으로 메시지 문자열을 f-string 템플릿으로 해석해서
    `{`/`}`를 변수 자리로 취급한다. JSON 스키마·SKILL.md 등 우리가 끼워 넣는 텍스트는
    변수가 아니라 순수 문자열이므로, 중괄호를 이스케이프해서 리터럴로 살아남게 한다."""
    return text.replace("{", "{{").replace("}", "}}")


def _build_user_messages(
    *,
    period: str,
    line_label: str,
    equipment_label: str,
    images: list[str] | None,
    message: str | None = None,
) -> tuple[list[BaseMessage], str]:
    """에이전트에 넘길 human 메시지와, 대화 기록에 남길 '텍스트만' 버전을 함께 만든다.

    반환값을 둘로 나눈 이유가 이 함수의 핵심이다:
      - 프롬프트(첫 번째 반환값)에는 이미지가 들어가야 한다.
      - 대화 기록(두 번째 반환값)에는 이미지가 절대 들어가면 안 된다.
        들어가면 같은 session_id로 다음 요청을 할 때 base64가 통째로 다시 전송돼
        비용·지연이 요청마다 누적된다.

    이미지가 없으면 content를 '문자열'로 둔다 = 기존과 완전히 같은 경로(회귀 없음).
    이미지가 있으면 content를 '리스트'로 만든다 (text 조각 + image_url 조각들).

    message: AI 원인분석 대화형 화면에서 사용자가 직접 입력한 자유 텍스트 질문 (F-07).
        없으면(기본값 None) 아래 텍스트가 예전과 한 글자도 다르지 않다 — 회귀 없음.
    """
    text = (
        "아래 조건에 해당하는 정지 기록을 MCP 도구로 조회하고, 원인 분석 리포트를 생성해줘.\n"
        f"- 기간: {period}\n- 라인: {line_label}\n- 설비: {equipment_label}"
    )

    if message:
        text += (
            f"\n\n사용자 질문: {message}\n"
            "위 질문에 특히 집중해서 답해라 — recommended_action·confidence_note에 질문에 대한 답을 반영해라."
        )

    if not images:
        # 이미지가 없을 때의 프롬프트는 기존과 한 글자도 다르지 않다.
        return [HumanMessage(content=text)], text

    text += (
        f"\n\n첨부 이미지 {len(images)}장도 함께 참고해라.\n"
        "- 이미지에서 읽어낸 사실(에러코드·설비ID·시각·화면 문구·눈에 보이는 손상 등)은"
        " visual_findings에 한 줄씩 적어라.\n"
        "- 이미지에 없는 내용을 추측해서 채우지 마라. 못 읽으면 빈 목록으로 둔다.\n"
        "- 이미지의 설비ID가 위 조건과 다르면 위 조건을 따르고, 불일치를 confidence_note에 적어라."
    )

    content: list[Any] = [{"type": "text", "text": text}]
    for data_url in images:
        content.append({"type": "image_url", "image_url": {"url": data_url}})

    return [HumanMessage(content=content)], text


def _build_prompt(schema_json: str, extra_instruction: str = "") -> ChatPromptTemplate:
    system = (
        "너는 제조 현장 설비 다운타임 원인 분석 에이전트다.\n\n"
        "# 도메인 규칙 (반드시 따를 것)\n"
        f"{_escape_braces(_load_skill_text())}\n\n"
        "# 출력 형식\n"
        "위 규칙과 도구 조회 결과를 근거로, 아래 JSON 스키마를 그대로 따르는 JSON 객체 하나만 출력해라. "
        "설명 문장이나 마크다운 코드펜스 없이 순수 JSON만 반환한다.\n"
        f"{_escape_braces(schema_json)}"
        + (f"\n\n{_escape_braces(extra_instruction)}" if extra_instruction else "")
    )
    return ChatPromptTemplate.from_messages(
        [
            ("system", system),
            MessagesPlaceholder("chat_history", optional=True),
            # ⚠️ 여기를 ("human", "{input}") 으로 되돌리면 이미지가 조용히 사라진다.
            #    ("human", "...") 은 문자열 f-string 템플릿이라, {input} 자리에 리스트를 넣으면
            #    리스트가 str()로 변환돼 "[{'type': 'text', ...}]" 같은 '글자'가 된다.
            #    에러가 안 나기 때문에 눈치채기 어렵다 (tests/test_multimodal.py AC-02가 이걸 잡는다).
            #    MessagesPlaceholder는 메시지 객체를 그대로 통과시켜 content가 리스트로 유지된다.
            MessagesPlaceholder("input"),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )


def _escape_inner_quotes(text: str) -> str:
    """문자열 값 안의 이스케이프 안 된 따옴표를 고쳐서 JSON을 살린다.

    왜 필요한가:
      모델이 evidence 같은 자연어 칸에 따옴표를 그대로 써서 보내는 일이 잦다.
        {"evidence": "로그에 "E-102" 기록됨"}   ← 두 번째 따옴표에서 파싱이 깨진다
      json.JSONDecodeError("Expecting ',' delimiter")로 나타난다.
      모델을 바꿀 때마다 재발하므로(무료 모델일수록 잦다) 한 번 고쳐 둔다.

    판별 방법:
      문자열 안에서 만난 따옴표 뒤에 (공백을 건너뛰고) , } ] : 또는 끝이 오면
      진짜 닫는 따옴표다. 그 외에는 값 안에 들어간 따옴표이므로 이스케이프한다.
      완벽한 파서는 아니지만 이 실패 유형은 확실히 잡는다.
    """
    out: list[str] = []
    in_string = False
    escaped = False
    for i, ch in enumerate(text):
        if escaped:
            out.append(ch)
            escaped = False
            continue
        if ch == "\\":
            out.append(ch)
            escaped = True
            continue
        if ch == '"':
            if not in_string:
                in_string = True
                out.append(ch)
                continue
            nxt = next((c for c in text[i + 1:] if not c.isspace()), "")
            if nxt in (",", "}", "]", ":", ""):
                in_string = False
                out.append(ch)
            else:
                out.append('\\"')      # 값 안의 따옴표 — 이스케이프
            continue
        out.append(ch)
    return "".join(out)


def _extract_json(text: str) -> dict:
    """에이전트 최종 출력에서 JSON 객체를 뽑아낸다. 코드펜스가 섞여 나와도 처리한다."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if "\n" in cleaned:
            cleaned = cleaned.split("\n", 1)[1]
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        # 여는 중괄호는 있는데 닫는 게 없다 = max_tokens에 걸려 잘렸을 가능성이 크다.
        # 그냥 "JSON 못 찾음"으로 두면 원인을 못 찾으므로 구분해서 알린다.
        if start != -1 and end == -1:
            raise ValueError(
                f"응답이 중간에 끊겼습니다 — MAX_OUTPUT_TOKENS({MAX_OUTPUT_TOKENS})에 걸렸을 수 있습니다. "
                f"출력 길이 {len(cleaned)}자"
            )
        raise ValueError("응답에서 JSON 객체를 찾지 못했습니다")
    candidate = cleaned[start : end + 1]

    # 닫는 괄호가 모자라면 잘린 것이다.
    # 위의 end == -1 검사만으로는 못 잡는다: 안쪽 객체의 }가 이미 여러 개 있어서
    # rfind("}")가 그중 마지막을 잡고 검사를 통과해버린다. 그러면 잘림이
    # "Expecting ',' delimiter" 같은 문법 오류로 보여 원인을 잘못 짚게 된다(실제로 그랬다).
    if candidate.count("{") > candidate.count("}") or candidate.count("[") > candidate.count("]"):
        raise ValueError(
            f"응답이 중간에 끊겼습니다 — MAX_OUTPUT_TOKENS({MAX_OUTPUT_TOKENS})에 걸렸을 수 있습니다. "
            f"출력 길이 {len(cleaned)}자, 닫히지 않은 괄호 있음"
        )

    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        # 값 안의 따옴표 때문일 수 있다 — 고쳐서 한 번만 더 해본다.
        # 실패하면 원래 예외를 그대로 올려 재시도 사다리가 돌게 한다.
        try:
            repaired = json.loads(_escape_inner_quotes(candidate))
        except json.JSONDecodeError:
            # 실패한 자리 주변을 남긴다.
            # 왜: 에러 메시지는 위치(line/column)만 알려주고 그 자리에 무엇이 있었는지는
            #   안 알려준다. 그게 없으면 "따옴표 때문인지 다른 이유인지"를 추측할 수밖에 없다.
            #   실제로 이것 때문에 원인을 세 번 잘못 짚었다.
            around = candidate[max(0, exc.pos - 250): exc.pos + 250]
            logger.error(
                "JSON 파싱 실패 (%s) — 전체 %d자, 실패 위치 %d. 주변 원문:\n%s",
                exc, len(candidate), exc.pos, around,
            )
            raise exc
        logger.info("JSON 문자열 안의 따옴표를 고쳐 파싱에 성공했습니다 (%s)", exc.msg)
        return repaired


# 마지막 리포트 생성에서 에이전트가 도구를 몇 번 불렀는지.
# 왜 남기나: 같은 입력인데 응답이 8초 걸릴 때와 29초 걸릴 때가 있었다.
#   모델이 느린 건지, 도구를 여러 번 왕복한 건지 구분하려면 이 횟수가 필요하다.
#   (Langfuse 트레이스로도 보이지만, 평가 스크립트가 케이스마다 바로 찍으려면
#    코드에서 꺼낼 수 있어야 한다)
_LAST_AGENT_STEPS: int | None = None


def last_agent_steps() -> int | None:
    """마지막 실행의 도구 호출 횟수. 폴백이면 None일 수 있다."""
    return _LAST_AGENT_STEPS


async def _run_agent_json(
    tools: list,
    llm: ChatOpenAI,
    schema_json: str,
    user_messages: list[BaseMessage],
    chat_history: list[BaseMessage],
    run_config: dict,
    extra_instruction: str = "",
) -> dict:
    prompt = _build_prompt(schema_json, extra_instruction)
    agent = create_tool_calling_agent(llm, tools, prompt)
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        max_iterations=AGENT_MAX_ITERATIONS,
        handle_parsing_errors=True,
        return_intermediate_steps=True,   # 도구 호출 횟수를 세기 위해
    )
#   LLM 호출 지점 — OpenRouter의 OpenAI 호환 API를 LangChain ChatOpenAI 로 호출한다.
# (에이전트가 MCP 도구를 고르고, 최종 응답을 여기서 받는다)
    # input은 이제 문자열이 아니라 메시지 목록이다 (이미지를 담을 수 있게).
    result = await executor.ainvoke(
        {"input": user_messages, "chat_history": chat_history},
        config=run_config,
    )
    global _LAST_AGENT_STEPS
    _LAST_AGENT_STEPS = len(result.get("intermediate_steps") or [])
    return _extract_json(result["output"])


# 마지막으로 발생한 인프라 오류. 폴백이 왜 났는지 밖에서 확인하는 용도다.
# (llm.py는 예외를 삼키고 폴백을 돌려주므로, 이게 없으면 호출한 쪽은
#  '재시도하면 풀릴 오류'인지 '백 번 해도 같은 오류'인지 구분할 수 없다.)
_LAST_INFRA_ERROR: dict | None = None

# 재시도해도 소용없는 상태 코드.
#   401 키 만료·무효 / 403 권한 없음 / 404 라우팅 불가(모델·설정 문제)
#   / 400 요청 자체가 잘못됨
# 반대로 429(요청 몰림)·402(정산 대기)·500·503(서버 혼잡)은 기다리면 풀릴 수 있다.
PERMANENT_STATUS = frozenset({400, 401, 403, 404})


def _record_last_infra_error(roots: list[BaseException]) -> None:
    global _LAST_INFRA_ERROR
    exc = roots[0] if roots else None
    status = getattr(exc, "status_code", None)
    _LAST_INFRA_ERROR = {
        "type": type(exc).__name__ if exc else None,
        "message": str(exc)[:300] if exc else "",
        "status_code": status,
        "permanent": status in PERMANENT_STATUS,
    }


def last_infra_error() -> dict | None:
    """마지막 인프라 오류 정보. 폴백이 아닌 정상 응답 뒤에는 옛 값이 남아 있을 수 있으니
    '폴백이 났을 때'에만 참고한다. permanent=True면 재시도가 의미 없다."""
    return _LAST_INFRA_ERROR


def _root_causes(exc: BaseException) -> list[BaseException]:
    """ExceptionGroup 안에 든 '진짜' 예외들을 평평하게 펴서 돌려준다.

    왜 필요한가 (여기서 한 번 데였다):
      MCP 클라이언트는 내부에서 anyio TaskGroup을 쓴다. 그 안에서 예외가 나면
      ExceptionGroup에 싸여 올라오는데, ExceptionGroup은 str()이
      "unhandled errors in a TaskGroup (1 sub-exception)" 로만 나온다.
      그래서 `logger.error("...: %s", exc)` 로 찍으면 진짜 원인(예: HTTP 402,
      429, 인증 실패)이 로그에 한 글자도 안 남는다 — 운영 중 원인 추적이 불가능해진다.
      실제로 평가 실행 중 402(크레딧 소진)를 이 때문에 못 찾아 따로 진단해야 했다.

    중첩될 수 있으므로(그룹 안의 그룹) 재귀로 내려간다.
    """
    subs = getattr(exc, "exceptions", None)
    if not subs:
        return [exc]
    flat: list[BaseException] = []
    for sub in subs:
        flat.extend(_root_causes(sub))
    return flat


class AnalysisInfrastructureError(RuntimeError):
    """분석 인프라 또는 분석 응답 생성이 실패해 리포트를 만들 수 없을 때."""


async def _generate_with_retries(
    tools: list,
    llm: ChatOpenAI,
    run_config: dict,
    user_messages: list[BaseMessage],
    chat_history: list[BaseMessage],
    equipment_label: str,
    line_label: str,
    period: str,
) -> DowntimeReport:
    """3단계 출력 검증 재시도. 모두 실패하면 분석 예외를 호출자에게 전달한다."""
    full_schema = json.dumps(DowntimeReport.model_json_schema(), ensure_ascii=False)
    simplified_schema = json.dumps(_SimplifiedReport.model_json_schema(), ensure_ascii=False)

    # ── 1차 시도 ──
    try:
        data = await _run_agent_json(tools, llm, full_schema, user_messages, chat_history, run_config)
        return DowntimeReport.model_validate(data)
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("1차 리포트 생성 실패, 프롬프트 재시도: %s", exc)

    # ── 2차 시도: 프롬프트 재시도 (동일 스키마) ──
    try:
        data = await _run_agent_json(
            tools,
            llm,
            full_schema,
            user_messages,
            chat_history,
            run_config,
            extra_instruction=(
                "방금 응답이 스키마를 지키지 못했다. 반드시 JSON 스키마 그대로, "
                "다른 텍스트 없이 JSON 객체 하나만 다시 응답해라."
            ),
        )
        return DowntimeReport.model_validate(data)
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("2차 리포트 생성 실패, 축소 스키마로 재시도: %s", exc)

    # ── 3차 시도: 축소 스키마로 재시도 ──
    try:
        data = await _run_agent_json(
            tools,
            llm,
            simplified_schema,
            user_messages,
            chat_history,
            run_config,
            extra_instruction="구조가 복잡해 계속 실패했을 수 있다. 더 단순한 스키마로 다시 응답해라.",
        )
        simplified = _SimplifiedReport.model_validate(data)
        return DowntimeReport(
            equipment_id=simplified.equipment_id,
            line_id=simplified.line_id,
            period=simplified.period,
            causes=[],
            unclassified_count=simplified.unclassified_count,
            confidence_note=f"{simplified.confidence_note} (축소 스키마 응답 — {simplified.summary})",
            recommended_action=simplified.recommended_action,
        )
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        logger.error("3차 리포트 생성도 실패: %s", exc)

    # 분석 실패를 정상적인 빈 리포트로 바꾸지 않는다. 라우터가 503으로 변환해
    # 프론트의 기존 오류 처리 경로를 타게 하고, 저장/리포트 ID도 만들지 않는다.
    raise AnalysisInfrastructureError("분석 결과를 생성하지 못했습니다")


async def generate_report(
    *,
    line_id: str | None = None,
    equipment_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    trace_session_id: str | None = None,
    images: list[str] | None = None,
    message: str | None = None,
    report_id: str | None = None,
) -> DowntimeReport:
    """조건에 맞는 정지 기록을 MCP 도구로 조회해 원인 분석 리포트를 생성한다.

    session_id를 주면 같은 세션의 이전 대화를 프롬프트에 같이 넣어 후속 질문에
    맥락을 유지한다 (F-07, docs/MESTORY_기능목록.md 참고). 대화 기록은 이제
    backend/db.py(Postgres)에 저장되므로 재배포해도 남는다.

    images: 이미지 data URL 목록 (예: "data:image/png;base64,..."). 주면 LLM이
        텍스트 조건·MCP 조회 결과와 함께 이미지도 근거로 본다 (docs/specs/multimodal.md).
        형식·용량 검증은 라우터(backend/main.py)에서 끝내고 오므로 여기서는 담기만 한다.

    message: AI 원인분석 대화형 화면의 자유 텍스트 질문 (F-07). 없어도 기존 리포트
        생성 흐름과 동일하게 동작한다.

    report_id: main.py가 미리 만들어 건네는 ID. DB에 리포트를 저장할 때 이 ID를 쓰고,
        main.py는 응답 헤더(X-Report-Id)로 프론트에 같은 ID를 돌려줘서 "상세 리포트
        보기"가 재조회 없이 바로 이 리포트를 가리킬 수 있게 한다.
    """
    period = f"{date_from or '전체'} ~ {date_to or '전체'}"
    equipment_label = equipment_id or (f"{line_id} 전체 설비" if line_id else "전체 설비")
    line_label = line_id or "전체 라인"

    has_images = bool(images)

    # 프롬프트용 메시지(이미지 포함)와 기록용 텍스트(이미지 제외)를 따로 받는다.
    user_messages, history_text = _build_user_messages(
        period=period,
        line_label=line_label,
        equipment_label=equipment_label,
        images=images,
        message=message,
    )

    chat_history = await load_chat_history(session_id, _SESSION_HISTORY_LIMIT) if session_id else []
    # Langfuse에서 트레이스를 묶는 이름과, 대화 기록을 묶는 session_id는 별개다.
    #
    # 왜 나눴나 (Windows에서 막혔다):
    #   session_id를 주면 DB(psycopg)에서 대화 기록을 찾는데, psycopg 비동기는
    #   Windows에서 SelectorEventLoop를 요구한다. 그런데 MCP 서버는 서브프로세스로
    #   띄우므로 ProactorEventLoop가 필요하다 — 둘을 동시에 만족시킬 수 없다.
    #   평가 스크립트는 '트레이스를 회차별로 묶는 이름표'만 필요하고 대화 기록은
    #   필요 없으므로, DB를 타지 않는 별도 인자를 둔다.
    run_config = _build_run_config(
        trace_session_id or session_id, line_id, equipment_id, user_id
    )

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", MCP_SERVER_MODULE],
        cwd=str(REPO_ROOT),
        env=_mcp_subprocess_env(),
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await load_mcp_tools(session)
                if not tools:
                    logger.warning("MCP 서버에 등록된 도구가 없습니다 (mcp_server/server.py 구현 대기 중)")

                llm = _build_llm()
                report = await _generate_with_retries(
                    tools, llm, run_config, user_messages, chat_history, equipment_label, line_label, period
                )
    except BaseException as exc:  # MCP 연결/프로세스 기동 실패 등 인프라 레벨 오류
        # ExceptionGroup은 Exception이 아닐 수 있어 BaseException으로 받는다.
        # (KeyboardInterrupt 등은 아래에서 그대로 다시 올린다)
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        roots = _root_causes(exc)
        causes = "; ".join(f"{type(c).__name__}: {c}" for c in roots)
        # 호출한 쪽(평가 스크립트 등)이 '재시도해도 소용없는 오류인지' 판단할 수 있게
        # 마지막 원인을 남겨 둔다. 폴백 리포트만 보면 상태 코드를 알 수 없기 때문이다.
        _record_last_infra_error(roots)
        logger.error(
            "MCP 연결 또는 에이전트 실행 중 오류를 호출자에게 전달합니다: %s", causes, exc_info=exc
        )
        raise AnalysisInfrastructureError("분석 인프라에 연결할 수 없습니다") from exc

    # equipment_id/line_id/period는 사용자가 준 조건이 정답이다 — LLM 출력으로 덮어쓰지 않는다.
    report.equipment_id = equipment_label
    report.line_id = line_label
    report.period = period

    # used_image도 같은 원칙. LLM이 "이미지를 봤다"고 말해도 믿지 않고, 실제로 넘겼는지로 정한다.
    report.used_image = has_images
    if not has_images:
        # 이미지가 없으면 visual_findings는 무조건 null. LLM이 뭔가 채워 보냈어도 지운다.
        report.visual_findings = None

    if report_id:
        await save_report(report_id, report, session_id)

    if session_id:
        # ⚠️ 대화 기록(content)에는 '텍스트만' 넣는다 (content가 리스트여도 text 조각만).
        #    이미지 base64를 넣으면 다음 요청마다 그 덩어리가 통째로 다시 LLM에 전송돼
        #    비용·지연이 요청마다 누적된다 (tests/test_multimodal.py AC-10이 이걸 잡는다).
        #    content는 LLM이 다음 턴에 참고할 전체 프롬프트/JSON 그대로 두고,
        #    display_content만 화면에 보여줄 짧은 문장으로 따로 저장한다 —
        #    안 그러면 새로고침 후 채팅창에 원본 프롬프트·리포트 JSON이 그대로 노출된다.
        #    질문 없이 조건만으로 요청하거나 recommended_action이 비면 display_content가
        #    None이 돼 원본 프롬프트/JSON이 다시 노출되므로, 짧은 대체 문장을 채워 둔다.
        user_display = message or f"{period} · {line_label} · {equipment_label} 원인 분석 요청"
        assistant_display = report.recommended_action or "원인 분석 리포트가 생성되었습니다."
        await save_message(session_id, "user", history_text, display_content=user_display)
        await save_message(
            session_id, "assistant", report.model_dump_json(),
            report_id=report_id, display_content=assistant_display,
        )

    return report
