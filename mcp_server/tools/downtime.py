"""
창구 ①: 정지 로그 조회  (팀 PRD F-01)

누가 부르나
  - LangChain 에이전트(AI)가 필요하다고 판단할 때 스스로 골라 부른다 (팀 PRD 7장).
  - 그래서 AI가 조건을 조금 다르게 써도(예: "line-a") 알아듣게 하고,
    어떤 조건으로 조회했는지 결과에 다시 적어 준다.

하는 일
  - 기간(날짜), 라인, 설비 조건으로 정지 기록을 골라낸다. (PRD F-01 기본 조건)
  - 에러코드, 정지시간 조건도 추가로 받는다. (같은 코드 반복 여부 확인용, SKILL.md 판단 기준)
  - 조건은 전부 "선택"이다. 준 조건만 적용하고, 여러 개를 주면 모두 맞는 행만 남긴다(AND).
  - 날짜는 "정지가 시작된 날" 기준이다. 자정을 넘긴 정지는 시작한 날에만 잡힌다.

아직 안 하는 일 (다음 단계에서 추가)
  - 요약 통계 (건수, 합계 시간, 코드별 집계, 계획 정지 구분)  → PRD F-13 의 재료
  - 이상한 기록 표시 (음수 시간, 빈 코드, 미등록 코드, 없는 설비, 라인 불일치) → PRD F-05
"""

from datetime import date

import pandas as pd

# 같은 폴더(tools)의 data_loader.py 에서 정지 로그 읽는 함수를 가져온다
from .data_loader import load_downtime_logs

# 한 번에 돌려줄 최대 행 수.
# 조건 없이 부르면 14,099행이 통째로 나가서 LLM 비용이 폭증하므로 상한을 둔다.
DEFAULT_LIMIT = 200
MAX_LIMIT = 1000

# 결과로 돌려줄 컬럼 (계산용 _start_dt 는 빼고 원래 컬럼만)
OUTPUT_COLUMNS = [
    "log_id", "line_id", "equipment_id", "start_time", "end_time",
    "downtime_min", "error_code", "shift", "operator_note",
]


# ─────────────────────────────────────────────
# 보조 함수: 날짜 글자를 검사하고 날짜로 바꾸기
# ─────────────────────────────────────────────
def _parse_date(value: str, field_name: str) -> date:
    """'2026-08-10' 같은 글자를 날짜로 바꾼다. 형식이 틀리면 알기 쉬운 에러를 낸다."""
    try:
        # date.fromisoformat = "YYYY-MM-DD" 형식의 글자를 날짜로 바꿔 주는 함수
        return date.fromisoformat(value)
    except ValueError:
        # raise = 에러를 일부러 발생시킴. 잘못된 입력을 조용히 넘기지 않기 위해서다.
        raise ValueError(f"{field_name} 형식이 잘못됐습니다: '{value}' (예: 2026-08-10)")


def _normalize_id(value: str | None) -> str | None:
    """ID 글자를 표준 모양으로 맞춘다. 예: ' line-a ' → 'LINE-A'

    왜 필요한가?
      AI가 도구를 부를 때 소문자나 공백을 섞어 보낼 수 있다.
      데이터의 ID는 전부 대문자(LINE-A, EQ-001, E-102)라서,
      그대로 비교하면 기록이 있는데도 0건이 나온다.
    """
    if value is None:
        return None
    # .strip() = 앞뒤 공백 제거, .upper() = 대문자로 변환
    cleaned = value.strip().upper()
    # 공백만 들어온 경우("  ")는 조건을 안 준 것으로 본다
    return cleaned or None


# ─────────────────────────────────────────────
# 메인 함수: 정지 로그 조회
# ─────────────────────────────────────────────
def query_downtime_logs(
    date_from: str | None = None,        # 시작 날짜 (이 날 포함). 예: "2026-08-10"
    date_to: str | None = None,          # 끝 날짜 (이 날 포함). 예: "2026-08-10"
    line_id: str | None = None,          # 라인. 예: "LINE-A"
    equipment_id: str | None = None,     # 설비. 예: "EQ-001"
    error_code: str | None = None,       # 에러코드. 예: "E-102"
    min_downtime: float | None = None,   # 정지시간 최소(분, 이상)
    max_downtime: float | None = None,   # 정지시간 최대(분, 이하)
    limit: int = DEFAULT_LIMIT,          # 돌려줄 최대 행 수
) -> dict:
    """조건에 맞는 정지 기록을 골라 돌려준다.

    `str | None = None` 의 뜻
      - 글자(str)를 받거나, 안 주면(None) 기본값 None 이 된다.
      - None 인 조건은 "적용하지 않음"으로 처리한다.

    돌려주는 모양
      {
        "applied_filters": 실제로 적용한 조건 (AI가 무엇으로 조회했는지 확인용),
        "total_count":    조건에 맞는 전체 행 수,
        "returned_count": 실제로 돌려준 행 수 (limit 때문에 더 적을 수 있음),
        "truncated":      잘렸는지 여부 (True면 limit 때문에 일부만 보냄),
        "rows":           [ {log_id: ..., line_id: ..., ...}, ... ]
      }
    """

    # ── 1단계: 입력값 검사 ────────────────────
    # 잘못된 입력은 조회하기 전에 먼저 걸러낸다.
    start = _parse_date(date_from, "date_from") if date_from else None
    end = _parse_date(date_to, "date_to") if date_to else None

    if start and end and start > end:
        raise ValueError(f"date_from({date_from})이 date_to({date_to})보다 늦습니다.")

    if min_downtime is not None and max_downtime is not None and min_downtime > max_downtime:
        raise ValueError("min_downtime이 max_downtime보다 큽니다.")

    # limit이 너무 작거나 크면 허용 범위(1 ~ MAX_LIMIT) 안으로 맞춘다
    limit = max(1, min(limit, MAX_LIMIT))

    # ID 조건들을 표준 모양(대문자, 공백 제거)으로 맞춘다
    line_id = _normalize_id(line_id)
    equipment_id = _normalize_id(equipment_id)
    error_code = _normalize_id(error_code)

    # ── 2단계: 데이터 읽기 ────────────────────
    df = load_downtime_logs()

    # ── 3단계: 조건 걸러내기 ──────────────────
    # mask = 행마다 "남길지(True) / 뺄지(False)"를 적은 목록.
    # 처음엔 전부 True(모두 남김)로 시작하고, 조건을 하나씩 & (그리고) 로 덧붙인다.
    mask = pd.Series(True, index=df.index)

    # 날짜 조건: 시작 시각의 "날짜 부분"(.dt.date)만 비교한다.
    # 그래서 date_to="2026-08-10" 이면 8월 10일 23:59 기록까지 포함된다.
    if start:
        mask &= df["_start_dt"].dt.date >= start
    if end:
        mask &= df["_start_dt"].dt.date <= end

    # 글자 조건: 값이 정확히 같은 행만 남긴다
    if line_id:
        mask &= df["line_id"] == line_id
    if equipment_id:
        mask &= df["equipment_id"] == equipment_id
    if error_code:
        mask &= df["error_code"] == error_code

    # 숫자 조건: 0도 유효한 값이라서 "if min_downtime:" 이 아니라
    # "is not None" 으로 검사한다. (if 0: 은 False로 취급되기 때문)
    if min_downtime is not None:
        mask &= df["downtime_min"] >= min_downtime
    if max_downtime is not None:
        mask &= df["downtime_min"] <= max_downtime

    # mask 가 True 인 행만 남기고, 시작 시각 순서로 정렬한다
    # kind="stable": 시작 시각이 같은 행끼리는 원래 순서를 유지한다.
    #   → 같은 조건이면 항상 같은 순서로 나와서, 평가를 다시 돌려도 결과가 흔들리지 않는다.
    matched = df[mask].sort_values("_start_dt", kind="stable")

    # ── 4단계: 결과 만들기 ────────────────────
    total = len(matched)                       # 조건에 맞는 전체 행 수
    selected = matched.head(limit)             # 앞에서부터 limit 개만

    # to_dict("records") = 표를 [ {컬럼: 값, ...}, {...} ] 모양의 목록으로 바꿈
    # (MCP로 LLM에게 보낼 때는 이런 목록/사전 모양이어야 한다)
    rows = selected[OUTPUT_COLUMNS].to_dict("records")

    # 실제로 적용한 조건만 모아 둔다 (None 인 조건은 빼기)
    # {키: 값 for ... if 조건} = 조건에 맞는 것만 골라 사전을 만드는 짧은 문법
    applied_filters = {
        key: value
        for key, value in {
            "date_from": date_from,
            "date_to": date_to,
            "line_id": line_id,
            "equipment_id": equipment_id,
            "error_code": error_code,
            "min_downtime": min_downtime,
            "max_downtime": max_downtime,
        }.items()
        if value is not None and value != ""
    }

    return {
        "applied_filters": applied_filters,
        "total_count": total,
        "returned_count": len(rows),
        "truncated": total > len(rows),
        "rows": rows,
    }
