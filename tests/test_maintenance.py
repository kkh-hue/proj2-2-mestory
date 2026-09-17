"""
창구③ 정비이력 조회 시험 — docs/specs/maintenance-history.md 의 AC 를 그대로 옮긴 것.
"""

import pytest

from mcp_server.server import get_maintenance_history
from mcp_server.tools.data_loader import load_equipment
from mcp_server.tools.maintenance import query_maintenance_history

REF = "2026-09-10"   # 시험에서 쓰는 리포트 기준 날짜


def test_ac01_기본_30일_조회():
    """AC-01: EQ-001, 9/10 기준 30일 → MT-00013 1건 (재발 위험, 5일 전)"""
    r = query_maintenance_history("EQ-001", REF)
    assert r["applied_filters"]["date_from"] == "2026-08-11"
    assert r["summary"]["record_count"] == 1

    row = r["rows"][0]
    assert row["maintenance_id"] == "MT-00013"
    assert row["flags"] == ["RECURRENCE_RISK"]
    assert row["days_before"] == 5


def test_ac02_긴_기간_요약():
    """AC-02: 180일 → 11건, 예방 4 / 사후 7, 재발위험 2, 재조치 1, 최신순"""
    r = query_maintenance_history("EQ-001", REF, days=180)
    s = r["summary"]
    assert s["record_count"] == 11
    assert (s["preventive_count"], s["corrective_count"]) == (4, 7)
    assert (s["recurrence_risk_count"], s["pending_rework_count"]) == (2, 1)
    assert s["last_maintenance_date"] == "2026-09-05"

    dates = [row["date"] for row in r["rows"]]
    # sorted(..., reverse=True) = 큰 값(최근 날짜)부터 정렬. 원래 순서와 같으면 최신순이다
    assert dates == sorted(dates, reverse=True)


def test_ac03_미래_기록_제외():
    """AC-03: 모든 설비에서, 기준 날짜보다 뒤의 기록이 하나도 없어야 한다"""
    for equipment_id in load_equipment()["equipment_id"]:
        for row in query_maintenance_history(equipment_id, REF, days=365)["rows"]:
            # 날짜 글자가 "YYYY-MM-DD" 모양이라 글자 비교로도 날짜 순서가 맞다
            assert row["date"] <= REF
            assert row["days_before"] >= 0


def test_ac04_기록_없음():
    """AC-04: 기간 안에 기록이 없으면 0건 + 안내 문구"""
    s = query_maintenance_history("EQ-001", "2026-01-01")["summary"]
    assert s["record_count"] == 0
    assert s["note"] == "최근 30일 동안 정비 기록이 없습니다."


def test_ac05_없는_설비():
    """AC-05: 설비 목록에 없는 설비 → 0건 + 경고 1개"""
    r = query_maintenance_history("eq-058", REF)
    assert r["summary"]["record_count"] == 0
    assert len(r["warnings"]) == 1
    assert "EQ-058" in r["warnings"][0]


@pytest.mark.parametrize("days, expected", [(999, 365), (0, 1)])
def test_ac06_days_범위(days, expected):
    """AC-06: days 가 범위 밖이면 1 ~ 365 로 맞춘다"""
    assert query_maintenance_history("EQ-001", REF, days=days)["applied_filters"]["days"] == expected


BAD_INPUTS = [
    {"equipment_id": "EQ-001", "reference_date": None},          # 기준 날짜 없음
    {"equipment_id": "EQ-001", "reference_date": "2026/09/10"},  # 날짜 형식 오류
    {"equipment_id": "", "reference_date": REF},                  # 설비 없음
]


@pytest.mark.parametrize("bad", BAD_INPUTS, ids=["날짜_없음", "날짜_형식", "설비_없음"])
def test_ac07_입력_오류(bad):
    """AC-07: 함수는 ValueError, MCP 도구는 error/hint dict"""
    with pytest.raises(ValueError):
        query_maintenance_history(**bad)

    result = get_maintenance_history(**bad)
    assert "error" in result and "hint" in result
