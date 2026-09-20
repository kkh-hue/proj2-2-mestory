"""리포트 조회 범위(라인·설비) 확정 — DB 없이 테스트할 수 있는 순수 함수.

설계는 docs/specs/report-scope.md 참고.
"""

from __future__ import annotations

import re

_EQUIPMENT_RE = re.compile(r"(?<![A-Za-z])EQ[-\s]?(\d{1,3})(?!\d)", re.IGNORECASE)
_LINE_CODE_RE = re.compile(r"(?<![A-Za-z])LINE[-\s]?([A-Z])(?![A-Za-z])", re.IGNORECASE)
_LINE_KOREAN_RE = re.compile(r"(?<![A-Za-z])([A-Za-z])\s?라인")

NEED_SCOPE_MESSAGE = "분석할 설비(예: EQ-057)나 라인(예: A라인)을 질문에 함께 적어 주세요."


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


def _equipment_by_type(
    text: str,
    line_hint: str | None,
    equipment_lines: dict[str, str] | None,
    equipment_types: dict[str, str],
) -> str | None:
    """질문 속 설비 종류 이름("컨베이어")으로 설비를 찾는다. 1대면 그 설비, 여러 대면 후보를 알려 준다."""
    mentioned = sorted({t for t in equipment_types.values() if t and t in text}, key=len, reverse=True)
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
