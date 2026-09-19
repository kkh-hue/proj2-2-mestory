"""다운타임 분석 화면(GET /downtime/analysis)의 집계 로직 — DB와 분리한 순수 함수.

DB 접속(psycopg) 없이 단위 테스트할 수 있게 backend/db.py에서 떼어 냈다.
설계는 docs/specs/downtime-analysis.md 참고.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

TOP_N = 4               # 원인별 막대에 따로 보여 줄 개수 (나머지는 "기타"로 묶는다)
DEFAULT_RANGE_DAYS = 7  # 기간을 안 주면 오늘 포함 최근 7일
UNREGISTERED_SUFFIX = " (사전 미등록)"


def resolve_period(date_from: date | None, date_to: date | None, today: date) -> tuple[date, date]:
    """조회 기간을 확정한다. date_to는 오늘보다 미래면 오늘로 자른다(시뮬레이션 데이터에 미래 행이 섞여 있다).

    date_from > date_to 를 사용자가 직접 준 경우에만 ValueError (라우터가 422로 바꾼다).
    """
    if date_from and date_to and date_from > date_to:
        raise ValueError("date_from은 date_to보다 늦을 수 없습니다.")
    end = min(date_to or today, today)
    start = date_from or end - timedelta(days=DEFAULT_RANGE_DAYS - 1)
    return start, end


def _percent(part: float, total: float) -> float:
    return round(part / total * 100, 1) if total > 0 else 0.0


def build_analysis(
    cause_rows: list[tuple],
    top_equipment_row: tuple | None,
    needs_review_count: int,
    date_from: date,
    date_to: date,
) -> dict:
    """DB에서 뽑은 원인별 합계 행들을 화면 응답 모양으로 만든다.

    cause_rows: (error_code, description|None, category|None, count, downtime_min, last_occurred|None)
        description이 None이면 error_code_dict에 없는 코드다.
    top_equipment_row: (equipment_id, equipment_type|None, downtime_min) 또는 None
    """
    causes = []
    for error_code, description, category, count, minutes, last_occurred in cause_rows:
        causes.append({
            "error_code": error_code,
            "label": description or f"{error_code}{UNREGISTERED_SUFFIX}",
            "category": category or "미분류",
            "count": int(count),
            "downtime_min": float(minutes),
            "last_occurred": last_occurred.isoformat() if isinstance(last_occurred, datetime) else None,
        })
    causes.sort(key=lambda c: (-c["downtime_min"], c["error_code"]))

    total = sum(c["downtime_min"] for c in causes)
    for cause in causes:
        cause["percent"] = _percent(cause["downtime_min"], total)

    breakdown = [
        {"label": c["label"], "category": c["category"], "percent": c["percent"]}
        for c in causes[:TOP_N]
    ]
    rest = causes[TOP_N:]
    if rest:
        breakdown.append({
            "label": "기타",
            "category": "기타",
            # 개별 반올림 값을 더하지 않고 시간 합계에서 다시 계산해 전체가 100%에 맞게 한다.
            "percent": _percent(sum(c["downtime_min"] for c in rest), total),
        })

    top_equipment = None
    if top_equipment_row:
        equipment_id, equipment_type, minutes = top_equipment_row
        top_equipment = {
            "equipment_id": equipment_id,
            "equipment_type": equipment_type,
            "downtime_min": float(minutes),
        }

    return {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "event_count": sum(c["count"] for c in causes),
        "total_downtime_min": round(total, 1),
        "top_equipment": top_equipment,
        "needs_review_count": int(needs_review_count),
        "breakdown": breakdown,
        "causes": causes,
    }
