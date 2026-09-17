"""LLM 호출은 이 파일 하나로 모읍니다.

라우터나 UI 코드가 openai를 직접 import하지 않게 하세요.
3차에서 이 파일 내부만 갈아끼우면 나머지는 그대로 돌아갑니다.

여기서 책임지는 것:
  - LangChain 도구 호출 에이전트(create_tool_calling_agent + AgentExecutor)로
    mcp_server가 제공하는 MCP 도구를 불러와 정지 로그/에러코드 사전/정비이력을 조회하고 리포트 생성
  - 출력 계약 검증 (Pydantic: DowntimeReport, DowntimeCause) — PRD 5-2
  - 실패 시 3단계 재시도/폴백: ① 프롬프트 재시도 → ② 축소 스키마 재시도 → ③ 고정 안전 응답
  - Langfuse 트레이스 남기기 (입력/출력/지연시간/토큰 사용량)
  - SKILL.md의 판단 규칙을 시스템 프롬프트로 주입

LangGraph는 이 프로젝트에서 금지되어 있어 사용하지 않는다 (docs/MESTORY_기능목록.md 범위 밖 참고).
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Literal

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_openai import ChatOpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import BaseModel, Field, ValidationError

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

FALLBACK_MESSAGE = "자동 분석 실패 — 원본 로그 확인 필요"

AGENT_MAX_ITERATIONS = 8  # 도구 호출 무한루프 방지용 상한


# ─────────────────────────────────────────────
# 출력 계약 (PRD 5-2, 필수 조건 3)
# ─────────────────────────────────────────────
class DowntimeCause(BaseModel):
    error_code: str = Field(description="원인으로 확정/추정한 에러코드")
    description: str = Field(description="원인에 대한 자연어 설명")
    severity: Literal["경미", "보통", "중대"] = Field(description="심각도")
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


# ─────────────────────────────────────────────
# 세션별 대화 기록 (F-07용 프로토타입)
#
# 지금은 프로세스 메모리의 dict 하나로 단순화했다. 서버가 재시작되면 사라지고,
# 여러 워커로 스케일 아웃하면 워커마다 따로 논다 — 그래서 "다음 세션에 수동으로
# 다시 주입"하는 것과 원리가 같다. 프로덕션에서는 이 dict 자리에 DB나 벡터DB 같은
# 영속 저장소가 들어가야 한다 (LangGraph는 이 프로젝트에서 안 쓰므로 LangGraph의
# store/checkpointer는 해당 없음 — docs/MESTORY_기능목록.md 범위 밖 참고).
# ─────────────────────────────────────────────
_SESSION_STORE: dict[str, list[BaseMessage]] = {}
_SESSION_HISTORY_LIMIT = 10  # 세션당 보관할 최근 메시지 수


def _load_skill_text() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def get_model_name() -> str:
    """main.py의 요청 로그에서도 같은 기본값을 쓰도록 노출한다."""
    return os.getenv("MESTORY_LLM_MODEL", "openai/gpt-4o-mini")


def _build_llm() -> ChatOpenAI:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY가 설정되지 않았습니다 (.env 확인)")
    return ChatOpenAI(
        model=get_model_name(),
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        temperature=0,
    )


def _build_run_config(session_id: str | None, line_id: str | None, equipment_id: str | None) -> dict:
    """AgentExecutor.ainvoke(config=...)에 넘길 값. Langfuse 콜백은 이제 생성자가 아니라
    invoke config의 metadata(langfuse_* 키)로 session_id/trace_name을 받는다."""
    if LangfuseCallbackHandler is None or not os.getenv("LANGFUSE_PUBLIC_KEY"):
        return {}
    metadata = {
        "langfuse_trace_name": "downtime_report",
        "line_id": line_id,
        "equipment_id": equipment_id,
    }
    if session_id:
        metadata["langfuse_session_id"] = session_id
    return {"callbacks": [LangfuseCallbackHandler()], "metadata": metadata}


def _escape_braces(text: str) -> str:
    """ChatPromptTemplate은 기본적으로 메시지 문자열을 f-string 템플릿으로 해석해서
    `{`/`}`를 변수 자리로 취급한다. JSON 스키마·SKILL.md 등 우리가 끼워 넣는 텍스트는
    변수가 아니라 순수 문자열이므로, 중괄호를 이스케이프해서 리터럴로 살아남게 한다."""
    return text.replace("{", "{{").replace("}", "}}")


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
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )


def _extract_json(text: str) -> dict:
    """에이전트 최종 출력에서 JSON 객체를 뽑아낸다. 코드펜스가 섞여 나와도 처리한다."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if "\n" in cleaned:
            cleaned = cleaned.split("\n", 1)[1]
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("응답에서 JSON 객체를 찾지 못했습니다")
    return json.loads(cleaned[start : end + 1])


async def _run_agent_json(
    tools: list,
    llm: ChatOpenAI,
    schema_json: str,
    user_input: str,
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
    )
    result = await executor.ainvoke(
        {"input": user_input, "chat_history": chat_history},
        config=run_config,
    )
    return _extract_json(result["output"])


def _fallback_report(equipment_id: str, line_id: str, period: str) -> DowntimeReport:
    return DowntimeReport(
        equipment_id=equipment_id,
        line_id=line_id,
        period=period,
        causes=[],
        unclassified_count=0,
        confidence_note=FALLBACK_MESSAGE,
        recommended_action=FALLBACK_MESSAGE,
    )


async def _generate_with_retries(
    tools: list,
    llm: ChatOpenAI,
    run_config: dict,
    user_input: str,
    chat_history: list[BaseMessage],
    equipment_label: str,
    line_label: str,
    period: str,
) -> DowntimeReport:
    """3단계 재시도/폴백 전략. 이 함수는 예외를 밖으로 내보내지 않고 항상 DowntimeReport를 반환한다."""
    full_schema = json.dumps(DowntimeReport.model_json_schema(), ensure_ascii=False)
    simplified_schema = json.dumps(_SimplifiedReport.model_json_schema(), ensure_ascii=False)

    # ── 1차 시도 ──
    try:
        data = await _run_agent_json(tools, llm, full_schema, user_input, chat_history, run_config)
        return DowntimeReport.model_validate(data)
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("1차 리포트 생성 실패, 프롬프트 재시도: %s", exc)

    # ── 2차 시도: 프롬프트 재시도 (동일 스키마) ──
    try:
        data = await _run_agent_json(
            tools,
            llm,
            full_schema,
            user_input,
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
            user_input,
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
        logger.error("3차 리포트 생성도 실패, 고정 안전 응답 반환: %s", exc)

    # ── 4차: 모두 실패 — 고정 안전 응답 ──
    return _fallback_report(equipment_label, line_label, period)


async def generate_report(
    *,
    line_id: str | None = None,
    equipment_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    session_id: str | None = None,
) -> DowntimeReport:
    """조건에 맞는 정지 기록을 MCP 도구로 조회해 원인 분석 리포트를 생성한다.

    session_id를 주면 같은 세션의 이전 대화를 프롬프트에 같이 넣어 후속 질문에
    맥락을 유지한다 (F-07, docs/MESTORY_기능목록.md 참고).
    """
    period = f"{date_from or '전체'} ~ {date_to or '전체'}"
    equipment_label = equipment_id or "전체 설비"
    line_label = line_id or "전체 라인"

    user_input = (
        "아래 조건에 해당하는 정지 기록을 MCP 도구로 조회하고, 원인 분석 리포트를 생성해줘.\n"
        f"- 기간: {period}\n- 라인: {line_label}\n- 설비: {equipment_label}"
    )

    chat_history = _SESSION_STORE.get(session_id, []) if session_id else []
    run_config = _build_run_config(session_id, line_id, equipment_id)

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", MCP_SERVER_MODULE],
        cwd=str(REPO_ROOT),
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
                    tools, llm, run_config, user_input, chat_history, equipment_label, line_label, period
                )
    except Exception as exc:  # MCP 연결/프로세스 기동 실패 등 인프라 레벨 오류
        logger.error("MCP 연결 또는 에이전트 실행 중 오류, 고정 안전 응답 반환: %s", exc)
        return _fallback_report(equipment_label, line_label, period)

    # equipment_id/line_id/period는 사용자가 준 조건이 정답이다 — LLM 출력으로 덮어쓰지 않는다.
    report.equipment_id = equipment_label
    report.line_id = line_label
    report.period = period

    if session_id:
        chat_history.append(HumanMessage(content=user_input))
        chat_history.append(AIMessage(content=report.model_dump_json()))
        _SESSION_STORE[session_id] = chat_history[-_SESSION_HISTORY_LIMIT:]

    return report
