"""
창구 ①: 정지 로그 조회  (팀 PRD F-01)

누가 부르나
  - LangChain 에이전트(AI)가 필요하다고 판단할 때 스스로 골라 부른다 (팀 PRD 7장).
  - 그래서 AI가 조건을 조금 다르게 써도(예: "line-a") 알아듣게 하고,
    어떤 조건으로 조회했는지 결과에 다시 적어 준다.

하는 일
  1) 조건으로 기록 골라내기
     - 기간(날짜), 라인, 설비 조건 (PRD F-01 기본 조건)
     - 에러코드, 정지시간 조건도 추가로 받는다 (같은 코드 반복 여부 확인용)
     - 조건은 전부 "선택"이다. 여러 개를 주면 모두 맞는 행만 남긴다(AND).
     - 날짜는 "정지가 시작된 날" 기준이다. 자정을 넘긴 정지는 시작한 날에만 잡힌다.
  2) 기록마다 설비 종류와 "주의 딱지(flags)"를 붙이기  (PRD F-05)
  3) 골라낸 기록 전체의 "사실 요약" 만들기  (PRD F-13 의 재료)
     - 건수·합계 시간·코드별 집계·계획 정지 구분만 계산한다.
     - 심각도 판단은 하지 않는다. (SKILL.md 규칙에 따라 AI/백엔드가 판단)

합계 규칙 (팀 결정 9/17)
  - 정지시간이 음수인 기록만 합계에서 뺀다. (더할 수 없는 잘못된 값)
  - 빈 코드·모르는 코드 기록도 "실제로 멈춘 시간"이므로 총 정지시간에는 넣는다.
    대신 코드별 집계에서는 빼고 "확인 필요" 목록으로 따로 보여준다.
  - 계획 정지(ETC-602)는 총 정지시간에 넣고, 코드별 집계(조치가 필요한 원인)에서는 뺀다.
"""

from datetime import date

import pandas as pd

# 같은 폴더(tools)의 data_loader.py 에서 파일 읽는 함수들을 가져온다
from .data_loader import load_downtime_logs, load_equipment, load_error_codes

# ─────────────────────────────────────────────
# 설정값 (바꿀 일이 생기면 여기만 고친다)
# ─────────────────────────────────────────────
# 한 번에 돌려줄 최대 행 수.
# 조건 없이 부르면 14,099행이 통째로 나가서 LLM 비용이 폭증하므로 상한을 둔다.
DEFAULT_LIMIT = 200
MAX_LIMIT = 1000

# "확인 필요" 목록도 너무 길어지지 않게 상한을 둔다
MAX_NEEDS_CHECK = 50

# 계획 정지 코드 목록.
# 사전(error_code_dict.csv)에서 ETC-602 의 분류 칸이 "기타"라서,
# 분류로는 계획 정지를 구분할 수 없다. 그래서 코드를 직접 적어 둔다.
# 계획 정지 코드가 늘어나면 이 목록에 추가한다. (SKILL.md 도 같이 수정)
PLANNED_STOP_CODES = {"ETC-602"}

# 사전에는 있지만 뜻이 "원인 모름"인 코드 (SKILL.md 예외와 함정, 팀 합의 대기)
UNKNOWN_CAUSE_CODES = {"ETC-604"}

# 주의 딱지(flags) 이름과 뜻.
# 이름은 영어 대문자로 고정해서 코드·테스트에서 비교하기 쉽게 하고,
# 사람이 읽을 설명은 따로 둔다.
FLAG_DESCRIPTIONS = {
    "NEGATIVE_DOWNTIME": "정지시간이 음수 (종료 시각이 시작보다 빠름) → 데이터 확인 요청, 합계에서 제외",
    "EMPTY_ERROR_CODE": "에러코드가 비어 있음 → 로그 기록 누락, 확인 필요",
    "UNREGISTERED_CODE": "에러코드 사전에 없는 코드 → 판정 불가, 현장 확인 필요",
    "UNKNOWN_CAUSE_CODE": "사전에 있지만 뜻이 '원인 미확인'인 코드 → 원인 추정 금지, 현장 확인 필요",
    "UNKNOWN_EQUIPMENT": "설비 목록에 없는 설비 → 설비 정보 없이 판단하지 않음",
    "LINE_MISMATCH": "로그의 라인과 설비 목록의 라인이 다름 → 데이터 확인 필요",
}

# "확인 필요" 목록에서 먼저 보여줄 순서 (숫자가 작을수록 먼저).
# ETC-604 같은 흔한 딱지가 목록을 꽉 채워서 진짜 데이터 오류가 가려지지 않게 한다.
FLAG_PRIORITY = {
    "NEGATIVE_DOWNTIME": 0,
    "EMPTY_ERROR_CODE": 0,
    "UNREGISTERED_CODE": 0,
    "UNKNOWN_EQUIPMENT": 1,
    "LINE_MISMATCH": 1,
    "UNKNOWN_CAUSE_CODE": 2,
}

# 이 딱지가 붙은 기록은 원인을 판정할 수 없으므로 "판정 불가 건수"에 센다.
# (팀 PRD 출력 계약의 unclassified_count 와 같은 뜻)
UNCLASSIFIED_FLAGS = {"NEGATIVE_DOWNTIME", "EMPTY_ERROR_CODE", "UNREGISTERED_CODE"}

# 이 딱지가 붙은 기록은 코드별 집계에서 뺀다 (원인 코드를 믿을 수 없어서)
EXCLUDE_FROM_CODE_SUMMARY = {"NEGATIVE_DOWNTIME", "EMPTY_ERROR_CODE", "UNREGISTERED_CODE"}

# 결과로 돌려줄 원래 컬럼 (계산용 _start_dt 는 빼기)
OUTPUT_COLUMNS = [
    "log_id", "line_id", "equipment_id", "start_time", "end_time",
    "downtime_min", "error_code", "shift", "operator_note",
]


# ─────────────────────────────────────────────
# 보조 함수 1: 날짜 글자를 검사하고 날짜로 바꾸기
# ─────────────────────────────────────────────
def _parse_date(value: str, field_name: str) -> date:
    """'2026-08-10' 같은 글자를 날짜로 바꾼다. 형식이 틀리면 알기 쉬운 에러를 낸다."""
    try:
        # date.fromisoformat = "YYYY-MM-DD" 형식의 글자를 날짜로 바꿔 주는 함수
        return date.fromisoformat(value)
    except ValueError:
        # raise = 에러를 일부러 발생시킴. 잘못된 입력을 조용히 넘기지 않기 위해서다.
        raise ValueError(f"{field_name} 형식이 잘못됐습니다: '{value}' (예: 2026-08-10)")


# ─────────────────────────────────────────────
# 보조 함수 2: ID 글자를 표준 모양으로 맞추기
# ─────────────────────────────────────────────
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
# 보조 함수 3: 기록 한 줄에 주의 딱지 붙이기
# ─────────────────────────────────────────────
def _make_flags(row, known_codes: set, equipment_lines: dict) -> list[str]:
    """기록 한 줄(row)을 보고, 해당하는 주의 딱지 이름들을 목록으로 돌려준다.

    한 기록에 딱지가 여러 개 붙을 수 있다.
    (예: LOG-014097 은 음수 정지시간 + 없는 설비)
    """
    flags = []
    code = row["error_code"].strip()

    # ① 정지시간이 음수인가?
    if row["downtime_min"] < 0:
        flags.append("NEGATIVE_DOWNTIME")

    # ② 에러코드가 비었나? / ③ 사전에 없는 코드인가? / ④ 원인 미확인 코드인가?
    if code == "":
        flags.append("EMPTY_ERROR_CODE")
    elif code not in known_codes:
        flags.append("UNREGISTERED_CODE")
    elif code in UNKNOWN_CAUSE_CODES:
        flags.append("UNKNOWN_CAUSE_CODE")

    # ⑤ 설비 목록에 없는 설비인가? / ⑥ 라인이 설비 목록과 다른가?
    # equipment_lines = {"EQ-001": "LINE-A", ...} (설비 → 원래 라인)
    master_line = equipment_lines.get(row["equipment_id"])  # 없으면 None
    if master_line is None:
        flags.append("UNKNOWN_EQUIPMENT")
    elif master_line != row["line_id"]:
        flags.append("LINE_MISMATCH")

    return flags


# ─────────────────────────────────────────────
# 보조 함수 4: 조건에 쓴 ID가 데이터에 아예 없는지 확인
# ─────────────────────────────────────────────
def _check_unknown_filters(
    df: pd.DataFrame, known_codes: set, equipment_lines: dict,
    line_id: str | None, equipment_id: str | None, error_code: str | None,
) -> list[str]:
    """AI가 존재하지 않는 라인·설비·코드로 조회했는지 확인해서 경고 문장을 만든다.

    왜 필요한가?
      결과가 0건일 때 "그날 정지가 없었다"인지 "ID를 잘못 넣었다"인지
      AI가 구분할 수 있어야 엉뚱한 결론을 내지 않는다.
    """
    warnings = []
    known_lines = set(df["line_id"]) | set(equipment_lines.values())
    known_equipment = set(df["equipment_id"]) | set(equipment_lines.keys())

    if line_id and line_id not in known_lines:
        warnings.append(f"라인 '{line_id}'는 데이터에 없습니다. 라인 ID를 확인하세요.")
    if equipment_id and equipment_id not in known_equipment:
        warnings.append(f"설비 '{equipment_id}'는 데이터에 없습니다. 설비 ID를 확인하세요.")
    if error_code and error_code not in known_codes and error_code not in set(df["error_code"]):
        warnings.append(f"에러코드 '{error_code}'는 사전과 로그 어디에도 없습니다.")
    return warnings


# ─────────────────────────────────────────────
# 보조 함수 5: 골라낸 기록 전체의 사실 요약 만들기
# ─────────────────────────────────────────────
def _summarize(matched: pd.DataFrame) -> dict:
    """flags 컬럼이 붙은 표(matched)를 받아 사실 요약을 만든다. 판단은 하지 않는다."""

    # 골라낸 기록이 0건이면 계산할 게 없으니 "0"으로 채운 요약을 바로 돌려준다
    # (빈 표로 계산을 이어가면 에러가 나기 때문)
    if len(matched) == 0:
        return {
            "record_count": 0,
            "total_downtime_min": 0.0,
            "planned_stop_count": 0,
            "planned_downtime_min": 0.0,
            "unplanned_downtime_min": 0.0,
            "unclassified_count": 0,
            "by_error_code": [],
            "flag_counts": {},
            "needs_check_count": 0,
            "needs_check": [],
            "flag_descriptions": {},
        }

    # 기록마다 "이 딱지를 가졌나?"를 True/False 로 계산해 두면 아래 계산이 쉬워진다
    # any(...) = 목록 안에 하나라도 해당하면 True
    has_negative = matched["flags"].apply(lambda f: "NEGATIVE_DOWNTIME" in f)
    is_unclassified = matched["flags"].apply(lambda f: any(x in UNCLASSIFIED_FLAGS for x in f))
    exclude_from_codes = matched["flags"].apply(lambda f: any(x in EXCLUDE_FROM_CODE_SUMMARY for x in f))
    is_planned = matched["is_planned_stop"]

    # 합계용 기록 = 음수만 뺀 나머지 (팀 결정)
    countable = matched[~has_negative]

    total_min = countable["downtime_min"].sum()
    planned_min = countable.loc[countable["is_planned_stop"], "downtime_min"].sum()

    # 코드별 집계용 기록 = 문제 딱지가 없고, 계획 정지가 아닌 기록
    for_codes = matched[~exclude_from_codes & ~is_planned]

    # groupby = 같은 에러코드끼리 묶기
    # agg     = 묶음마다 건수(count)와 합계(sum) 계산
    by_code = (
        for_codes.groupby("error_code")["downtime_min"]
        .agg(count="count", total_downtime_min="sum")
        .reset_index()                                   # 묶음 이름(error_code)을 다시 컬럼으로
        .sort_values(["total_downtime_min", "error_code"],
                     ascending=[False, True], kind="stable")  # 손실시간 큰 순, 같으면 코드 순
    )
    by_code["total_downtime_min"] = by_code["total_downtime_min"].round(1)

    # 확인 필요 목록 = 딱지가 하나라도 붙은 기록
    flagged = matched[matched["flags"].apply(len) > 0].copy()

    # 딱지 종류별 건수 (예: {"UNKNOWN_CAUSE_CODE": 641, "NEGATIVE_DOWNTIME": 2})
    # explode = 목록 칸을 한 줄에 하나씩 펼치기 → value_counts 로 세기
    flag_counts = flagged["flags"].explode().value_counts().sort_index().to_dict()

    # 중요한 딱지(데이터 오류)가 붙은 기록부터 보여주도록 정렬한다
    # min(...) = 그 기록의 딱지 중 가장 중요한(숫자가 작은) 순위
    flagged["_priority"] = flagged["flags"].apply(lambda f: min(FLAG_PRIORITY[x] for x in f))
    flagged = flagged.sort_values(["_priority", "_start_dt"], kind="stable")

    needs_check = [
        {
            "log_id": r["log_id"],
            "error_code": r["error_code"],
            "downtime_min": r["downtime_min"],
            "flags": r["flags"],
        }
        for _, r in flagged.head(MAX_NEEDS_CHECK).iterrows()
    ]

    return {
        "record_count": len(matched),                        # 골라낸 기록 수
        "total_downtime_min": round(float(total_min), 1),    # 총 정지시간 (음수 제외, 계획 정지 포함)
        "planned_stop_count": int((is_planned & ~has_negative).sum()),
        "planned_downtime_min": round(float(planned_min), 1),
        "unplanned_downtime_min": round(float(total_min - planned_min), 1),
        "unclassified_count": int(is_unclassified.sum()),    # 판정 불가 건수 (PRD 출력 계약과 같은 뜻)
        "by_error_code": by_code.to_dict("records"),         # 조치가 필요한 원인 후보 (손실시간 큰 순)
        "flag_counts": {k: int(v) for k, v in flag_counts.items()},  # 딱지 종류별 건수
        "needs_check_count": len(flagged),
        "needs_check": needs_check,                          # 딱지 붙은 기록 (최대 MAX_NEEDS_CHECK개)
        "flag_descriptions": {                               # 이번 결과에 나온 딱지의 뜻만 모아서
            name: FLAG_DESCRIPTIONS[name]
            for name in sorted({x for f in flagged["flags"] for x in f})
        },
    }


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
    """조건에 맞는 정지 기록과 그 사실 요약을 돌려준다.

    `str | None = None` 의 뜻
      - 글자(str)를 받거나, 안 주면(None) 기본값 None 이 된다.
      - None 인 조건은 "적용하지 않음"으로 처리한다.

    돌려주는 모양
      {
        "applied_filters": 실제로 적용한 조건,
        "warnings":       잘못된 ID 등 조회 조건에 대한 경고 (없으면 빈 목록),
        "summary":        골라낸 기록 "전체"의 사실 요약 (limit 과 상관없이 전체 기준),
        "total_count":    조건에 맞는 전체 행 수,
        "returned_count": 실제로 돌려준 행 수,
        "truncated":      limit 때문에 잘렸는지,
        "rows":           [ {원래 컬럼들 + equipment_type, is_planned_stop, flags}, ... ]
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
    known_codes = set(load_error_codes()["error_code"])      # 사전에 있는 코드 모음
    equipment = load_equipment()
    # 설비 → 라인, 설비 → 종류 를 빠르게 찾으려고 사전(dict)으로 만든다
    equipment_lines = dict(zip(equipment["equipment_id"], equipment["line_id"]))
    equipment_types = dict(zip(equipment["equipment_id"], equipment["equipment_type"]))

    # 조건에 쓴 ID가 데이터에 아예 없는지 먼저 확인
    warnings = _check_unknown_filters(df, known_codes, equipment_lines,
                                      line_id, equipment_id, error_code)

    # ── 3단계: 조건 걸러내기 ──────────────────
    # mask = 행마다 "남길지(True) / 뺄지(False)"를 적은 목록.
    # 처음엔 전부 True(모두 남김)로 시작하고, 조건을 하나씩 & (그리고) 로 덧붙인다.
    mask = pd.Series(True, index=df.index)

    # 날짜 조건: 시작 시각의 "날짜 부분"(.dt.date)만 비교한다.
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

    # 숫자 조건: 0도 유효한 값이라서 "is not None" 으로 검사한다
    if min_downtime is not None:
        mask &= df["downtime_min"] >= min_downtime
    if max_downtime is not None:
        mask &= df["downtime_min"] <= max_downtime

    # mask 가 True 인 행만 남기고, 시작 시각 순서로 정렬한다
    # kind="stable": 같은 시각끼리는 원래 순서 유지 → 다시 돌려도 결과가 같다
    # .copy(): 원본 표를 건드리지 않고 복사본에 컬럼을 추가하기 위해
    matched = df[mask].sort_values("_start_dt", kind="stable").copy()

    # ── 4단계: 기록마다 정보 붙이기 ───────────
    # .map(사전) = 값마다 사전에서 짝을 찾아 바꿈. 없는 설비는 NaN → fillna("")로 빈 글자
    matched["equipment_type"] = matched["equipment_id"].map(equipment_types).fillna("")
    matched["is_planned_stop"] = matched["error_code"].str.strip().isin(PLANNED_STOP_CODES)
    # 행 하나하나에 _make_flags 를 적용해서 딱지 목록을 만든다
    # (to_dict("records") = 행마다 {컬럼: 값} 사전으로 바꾼 목록 → for 로 하나씩 처리)
    matched["flags"] = [
        _make_flags(row, known_codes, equipment_lines)
        for row in matched.to_dict("records")
    ]

    # ── 5단계: 요약 만들기 (골라낸 "전체" 기준) ──
    summary = _summarize(matched)

    # ── 6단계: 결과 만들기 ────────────────────
    total = len(matched)
    selected = matched.head(limit)             # 앞에서부터 limit 개만
    rows = selected[OUTPUT_COLUMNS + ["equipment_type", "is_planned_stop", "flags"]].to_dict("records")

    # 실제로 적용한 조건만 모아 둔다 (None 인 조건은 빼기)
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
        "warnings": warnings,
        "summary": summary,
        "total_count": total,
        "returned_count": len(rows),
        "truncated": total > len(rows),
        "rows": rows,
    }
