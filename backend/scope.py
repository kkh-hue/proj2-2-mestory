"""리포트 조회 범위(라인·설비) 확정 — DB 없이 테스트할 수 있는 순수 함수.

설계는 docs/specs/report-scope.md 참고.
"""

from __future__ import annotations

import re

_EQUIPMENT_RE = re.compile(r"(?<![A-Za-z])EQ[-\s]?(\d{1,3})(?!\d)", re.IGNORECASE)
_LINE_CODE_RE = re.compile(r"(?<![A-Za-z])LINE[-\s]?([A-Z])(?![A-Za-z])", re.IGNORECASE)
_LINE_KOREAN_RE = re.compile(r"(?<![A-Za-z])([A-Za-z])\s?라인")

NEED_SCOPE_MESSAGE = "분석할 설비(예: EQ-057)나 라인(예: A라인)을 질문에 함께 적어 주세요."

# 설비 종류의 흔한 다른 표현(줄임말 등). "사출기"라고만 쓰는 사용자가 실제로 있는데,
# 마스터의 정식 이름("사출성형기")과 문자열이 정확히 겹치지 않으면 지금까지는 종류를 못 찾았다.
#
# ⚠️ 이건 RAG가 아니다 — LLM 프롬프트에 아무것도 넣지 않는다. resolve_scope()는 순수 함수로
# "어느 설비를 조회할지"만 정하고, 그 결과(EQ-057 등)만 아래 단계로 넘어간다. 임베딩 검색도
# 아니다 — 사전에 없는 표현은 추측하지 않고 그냥 "종류 없음"으로 둔다(모르는 걸 짐작해서
# 엉뚱한 설비를 조회하면 안 된다는 팀 규칙, AGENTS.md "조회 도구는 사실만 반환한다"와 같은 이유).
_TYPE_ALIASES: dict[str, tuple[str, ...]] = {
    "사출성형기": ("사출기", "사출 성형기", "사출성형"),
    "CNC가공기": ("CNC", "씨엔씨", "CNC 가공기", "CNC머신"),
    "비전검사기": ("비전", "비전 검사기", "비전카메라", "카메라검사기"),
    "컨베이어": ("콘베어", "컨베이어벨트", "컨베이어 벨트"),
    "포장기": ("포장기계", "패키징기", "패키징 기계"),
    "로봇암": ("로봇팔", "로봇 암"),
}


class ScopeError(ValueError):
    """범위를 확정할 수 없다. 메시지는 사용자에게 그대로 보여 줘도 되는 한국어 안내."""


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def _line_from_text(text: str) -> str | None:
    match = _LINE_CODE_RE.search(text) or _LINE_KOREAN_RE.search(text)
    return f"LINE-{match.group(1).upper()}" if match else None


def _equipment_from_text(text: str) -> str | None:
    match = _EQUIPMENT_RE.search(text)
    return f"EQ-{int(match.group(1)):03d}" if match else None


def _mentioned_types(text: str, known_types: set[str]) -> list[str]:
    """질문 문장에서 언급된 설비 종류(정식 이름)를 찾는다.

    1순위: 정식 이름이 그대로 들어 있으면 그것(기존 동작 그대로 — 가장 확실하다).
    2순위: 정식 이름이 하나도 안 걸리면, 그때만 흔한 다른 표현(_TYPE_ALIASES)을 본다.
           정식 이름이 이미 걸렸는데 별칭까지 더 찾으면, 서로 다른 종류가 섞여
           "여러 종류가 동시에 언급됨"처럼 보이는 오탐이 생길 수 있어 순서를 나눴다.
    """
    exact = {t for t in known_types if t in text}
    if exact:
        return sorted(exact, key=len, reverse=True)
    aliased = {
        canonical
        for canonical, aliases in _TYPE_ALIASES.items()
        if canonical in known_types and any(alias in text for alias in aliases)
    }
    return sorted(aliased, key=len, reverse=True)


def _equipment_by_type(
    text: str,
    line_hint: str | None,
    equipment_lines: dict[str, str] | None,
    equipment_types: dict[str, str],
) -> str | None:
    """질문 속 설비 종류 이름("컨베이어", "사출기")으로 설비를 찾는다. 1대면 그 설비, 여러 대면 후보를 알려 준다."""
    mentioned = _mentioned_types(text, {t for t in equipment_types.values() if t})
    if not mentioned:
        return None
    kind = mentioned[0]
    candidates = sorted(
        eq for eq, t in equipment_types.items()
        if t == kind and (not line_hint or (equipment_lines or {}).get(eq) == line_hint)
    )
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        shown = ", ".join(candidates[:8]) + (" 등" if len(candidates) > 8 else "")
        raise ScopeError(f"{kind} 설비가 {len(candidates)}대 있습니다({shown}). 설비 ID(예: {candidates[0]})를 함께 적어 주세요.")
    return None


def resolve_scope(
    message: str | None,
    line_id: str | None,
    equipment_id: str | None,
    equipment_lines: dict[str, str] | None,
    session_scope: tuple[str | None, str | None] | None,
    equipment_types: dict[str, str] | None = None,
) -> tuple[str | None, str | None]:
    """(line_id, equipment_id)를 확정해 돌려준다.

    우선순위: 요청 값 → 질문 속 설비/라인 → 세션의 마지막 범위.
    equipment_lines: {설비ID: 라인ID}. None이면 마스터를 못 읽은 것이라 검증·라인 채우기를 건너뛴다.
    equipment_types: {설비ID: 종류}. 주면 질문 속 종류 이름("컨베이어")으로 설비를 추론한다.
    session_scope: (line_id, equipment_id) — 같은 세션에서 마지막으로 확정된 범위.
    """
    line_id, equipment_id = _clean(line_id), _clean(equipment_id)
    text = message or ""
    text_line_id = _line_from_text(text)
    text_equipment_id = _equipment_from_text(text)

    if line_id and text_line_id and line_id != text_line_id:
        raise ScopeError(f"질문의 라인({text_line_id})과 요청 라인({line_id})이 일치하지 않습니다")
    if equipment_id and text_equipment_id and equipment_id != text_equipment_id:
        raise ScopeError(f"질문의 설비({text_equipment_id})와 요청 설비({equipment_id})가 일치하지 않습니다")

    if not equipment_id:
        equipment_id = text_equipment_id
    if not equipment_id and equipment_types and not session_scope and message:
        equipment_id = _equipment_by_type(text, line_id or _line_from_text(text), equipment_lines, equipment_types)
    if equipment_id and equipment_lines is not None and equipment_id not in equipment_lines:
        raise ScopeError(f"등록되지 않은 설비입니다: {equipment_id}")

    if not line_id and not equipment_id:
        line_id = _line_from_text(text)

    if not line_id and not equipment_id and session_scope:
        line_id, equipment_id = _clean(session_scope[0]), _clean(session_scope[1])

    # 설비가 정해졌으면 그 설비가 속한 라인이 정답이다 (질문·요청의 라인과 어긋나도 마스터를 따른다).
    if equipment_id and equipment_lines is not None:
        master_line_id = equipment_lines.get(equipment_id)
        if master_line_id is None:
            raise ScopeError(f"등록되지 않은 설비입니다: {equipment_id}")
        if text_line_id and text_line_id != master_line_id:
            raise ScopeError(f"설비({equipment_id})의 마스터 라인({master_line_id})과 질문 라인({text_line_id})이 일치하지 않습니다")
        if line_id and line_id != master_line_id:
            raise ScopeError(f"설비({equipment_id})의 마스터 라인({master_line_id})과 요청 라인({line_id})이 일치하지 않습니다")
        line_id = master_line_id

    if not line_id and not equipment_id:
        raise ScopeError(NEED_SCOPE_MESSAGE)
    return line_id, equipment_id
