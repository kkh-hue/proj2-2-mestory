"""
창구 ③: 정비이력 조회  (팀 PRD F-03)

누가 부르나
  - LangChain 에이전트(AI)가 "이 설비, 최근에 손본 적 있나? 같은 고장이 반복되나?"를
    확인하고 싶을 때 부른다.

하는 일
  - 설비 하나의 정비 기록을 "리포트 날짜 기준 최근 N일(기본 30일)" 만큼 돌려준다.
    (리포트 날짜보다 뒤에 있는 "미래" 정비 기록은 넣지 않는다)
  - 기록마다 주의 딱지를 붙인다.
      RECURRENCE_RISK : 결과가 "임시 조치, 재발 가능성 있음" → 이번 정지가 재발일 수 있음
      PENDING_REWORK  : 결과가 "부품 발주 후 재조치 예정"   → 아직 수리가 끝나지 않음
  - 사실 요약을 만든다 (건수, 예방/사후 건수, 딱지 건수, 가장 최근 정비일).

하지 않는 일
  - "이게 근본 원인이다" 같은 판단 (SKILL.md: 근본원인은 추정으로만 표기)

리포트 날짜(reference_date)가 없으면?
  - 에러로 알려준다 (팀 결정 9/17). 기준 날짜가 매번 같아야 평가를 다시 돌려도 결과가 같다.
"""

from datetime import timedelta

import pandas as pd

from .data_loader import load_equipment, load_maintenance
from .downtime import _normalize_id, _parse_date

# 기본으로 볼 기간(일)과 최대 기간
DEFAULT_DAYS = 30
MAX_DAYS = 365

# 한 번에 돌려줄 최대 기록 수 (설비 하나에 1년 치도 20건 이하라 충분)
MAX_LIMIT = 100

# 정비 결과 글자 → 주의 딱지 이름
# (결과 문구가 바뀌면 여기만 고친다)
RESULT_FLAGS = {
    "임시 조치, 재발 가능성 있음": "RECURRENCE_RISK",
    "부품 발주 후 재조치 예정": "PENDING_REWORK",
}

FLAG_DESCRIPTIONS = {
    "RECURRENCE_RISK": "임시 조치만 했고 재발 가능성이 기록됨 → 이번 정지가 재발일 가능성을 근거로 제시 (SKILL.md)",
    "PENDING_REWORK": "부품 발주 후 재조치 예정 → 수리가 아직 끝나지 않은 상태",
}


def query_maintenance_history(
    equipment_id: str,                     # 설비 (필수). 예: "EQ-001"
    reference_date: str | None = None,     # 리포트 날짜 (필수). 예: "2026-09-10"
    days: int = DEFAULT_DAYS,              # 리포트 날짜로부터 며칠 전까지 볼지
) -> dict:
    """설비 하나의 최근 정비 기록과 사실 요약을 돌려준다.

    예: query_maintenance_history("EQ-001", reference_date="2026-09-10")
        → 2026-08-11 ~ 2026-09-10 사이의 EQ-001 정비 기록

    돌려주는 모양
      {
        "applied_filters": {"equipment_id", "reference_date", "days", "date_from", "date_to"},
        "warnings": [ 설비 목록에 없는 설비일 때 경고 ],
        "summary": {
          "record_count", "preventive_count"(예방), "corrective_count"(사후),
          "recurrence_risk_count", "pending_rework_count",
          "last_maintenance_date", "last_corrective_date",
          "flag_descriptions", "note"
        },
        "rows": [ {maintenance_id, equipment_id, date, type, action_taken, result, days_before, flags}, ... ]
                 (최신 기록이 먼저)
      }
    """

    # ── 1단계: 입력값 검사 ────────────────────
    equipment_id = _normalize_id(equipment_id)
    if not equipment_id:
        raise ValueError("equipment_id 를 넣어 주세요. 예: \"EQ-001\"")

    if not reference_date:
        raise ValueError(
            "reference_date(리포트 날짜)를 넣어 주세요. 예: \"2026-09-10\" "
            "— 이 날짜 기준으로 최근 정비 기록을 찾습니다."
        )
    ref = _parse_date(reference_date, "reference_date")

    # days 가 이상한 값이면 1 ~ MAX_DAYS 사이로 맞춘다
    days = max(1, min(int(days), MAX_DAYS))

    # 조회 기간: (리포트 날짜 - days일) ~ 리포트 날짜  (양 끝 포함)
    # timedelta = 날짜 더하기·빼기용 "기간" 값
    start = ref - timedelta(days=days)

    # ── 2단계: 데이터 읽기 ────────────────────
    df = load_maintenance()
    known_equipment = set(load_equipment()["equipment_id"]) | set(df["equipment_id"])

    warnings = []
    if equipment_id not in known_equipment:
        warnings.append(f"설비 '{equipment_id}'는 데이터에 없습니다. 설비 ID를 확인하세요.")

    # ── 3단계: 조건 걸러내기 ──────────────────
    # 정비 날짜 글자("2026-08-02")를 진짜 날짜로 바꿔서 비교한다
    dates = pd.to_datetime(df["date"], errors="coerce").dt.date   # 잘못된 날짜는 NaT(값 없음)
    mask = (df["equipment_id"] == equipment_id) & (dates >= start) & (dates <= ref)

    matched = df[mask].copy()
    matched["_date"] = dates[mask]
    # 최신 기록이 먼저 오도록 정렬 (같은 날이면 기록 번호 순)
    matched = matched.sort_values(["_date", "maintenance_id"],
                                  ascending=[False, True], kind="stable")

    # ── 4단계: 기록마다 정보 붙이기 ───────────
    rows = []
    for rec in matched.head(MAX_LIMIT).to_dict("records"):
        flag = RESULT_FLAGS.get(rec["result"])          # 해당 결과가 아니면 None
        rows.append({
            "maintenance_id": rec["maintenance_id"],
            "equipment_id": rec["equipment_id"],
            "date": rec["date"],
            "type": rec["type"],                         # 예방 / 사후
            "action_taken": rec["action_taken"],
            "result": rec["result"],
            "days_before": (ref - rec["_date"]).days,    # 리포트 날짜로부터 며칠 전인가
            "flags": [flag] if flag else [],
        })

    # ── 5단계: 사실 요약 ──────────────────────
    def count_flag(name: str) -> int:
        return sum(1 for r in rows if name in r["flags"])

    corrective = [r for r in rows if r["type"] == "사후"]
    used_flags = sorted({f for r in rows for f in r["flags"]})

    summary = {
        "record_count": len(rows),
        "preventive_count": sum(1 for r in rows if r["type"] == "예방"),
        "corrective_count": len(corrective),
        "recurrence_risk_count": count_flag("RECURRENCE_RISK"),
        "pending_rework_count": count_flag("PENDING_REWORK"),
        # rows 는 최신순이라 첫 번째가 가장 최근 기록
        "last_maintenance_date": rows[0]["date"] if rows else None,
        "last_corrective_date": corrective[0]["date"] if corrective else None,
        "flag_descriptions": {name: FLAG_DESCRIPTIONS[name] for name in used_flags},
        # 기록이 없을 때 AI가 참고할 사실 (SKILL.md: 최근 정비 기록이 없으면 정기 점검 필요 언급)
        "note": (f"최근 {days}일 동안 정비 기록이 없습니다." if not rows else ""),
    }

    return {
        "applied_filters": {
            "equipment_id": equipment_id,
            "reference_date": ref.isoformat(),
            "days": days,
            "date_from": start.isoformat(),
            "date_to": ref.isoformat(),
        },
        "warnings": warnings,
        "summary": summary,
        "rows": rows,
    }
