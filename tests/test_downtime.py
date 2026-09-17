"""
창구① 정지 로그 조회 시험 — docs/specs/downtime-logs.md 의 AC 를 그대로 옮긴 것.

pytest 읽는 법
  - 이름이 test_ 로 시작하는 함수 하나 = 시험 하나
  - assert 조건  →  조건이 참이면 통과, 거짓이면 실패
  - pytest.raises(에러종류) →  "이 안에서 이 에러가 나야 통과"
"""

import pytest

from mcp_server.server import get_downtime_logs            # AI 가 부르는 도구 (에러를 dict 로 돌려줌)
from mcp_server.tools.downtime import query_downtime_logs  # 실제 조회 함수 (에러를 ValueError 로 냄)


# pytest.approx = 소수 계산의 아주 작은 오차는 같은 값으로 봐 주는 비교
# (예: 147.60000000001 == 147.6 으로 인정)


def test_ac01_조건_조회와_요약():
    """AC-01: 8/10 LINE-A → 8건, 147.6분, 계획정지 1건 41.9분, 판정불가 1건"""
    s = query_downtime_logs(date_from="2026-08-10", date_to="2026-08-10", line_id="LINE-A")["summary"]
    assert s["record_count"] == 8
    assert s["total_downtime_min"] == pytest.approx(147.6)
    assert s["planned_stop_count"] == 1
    assert s["planned_downtime_min"] == pytest.approx(41.9)
    assert s["unclassified_count"] == 1


def test_ac02_입력_정리():
    """AC-02: ' eq-001 ' 처럼 넣어도 EQ-001 로 정리되고, X-999 기록에 딱지가 붙는다"""
    r = query_downtime_logs(date_from="2026-08-10", date_to="2026-08-10", equipment_id=" eq-001 ")
    assert r["applied_filters"]["equipment_id"] == "EQ-001"
    assert r["total_count"] == 1
    assert "UNREGISTERED_CODE" in r["rows"][0]["flags"]


def test_ac03_데이터_오류_표시():
    """AC-03: 조건 없이 조회 → 전체 14099건과 딱지 개수가 정확해야 한다"""
    s = query_downtime_logs()["summary"]
    assert s["record_count"] == 14099
    assert s["total_downtime_min"] == pytest.approx(337695.7)
    assert s["flag_counts"] == {
        "EMPTY_ERROR_CODE": 2,
        "LINE_MISMATCH": 3,
        "NEGATIVE_DOWNTIME": 2,
        "UNKNOWN_CAUSE_CODE": 641,
        "UNKNOWN_EQUIPMENT": 1,
        "UNREGISTERED_CODE": 2,
    }


def test_ac04_음수_정지시간은_합계에서_제외():
    """AC-04: 음수 기록 2건 모두 딱지가 붙고, 합계는 0"""
    r = query_downtime_logs(max_downtime=-1)
    assert r["total_count"] == 2
    # all(...) = 목록의 모든 값이 참인지 확인
    assert all("NEGATIVE_DOWNTIME" in row["flags"] for row in r["rows"])
    assert r["summary"]["total_downtime_min"] == 0


def test_ac05_없는_ID는_경고():
    """AC-05: 없는 설비로 조회하면 0건 + 경고 1개 (0건을 '정지 없음'으로 오해하지 않게)"""
    r = query_downtime_logs(equipment_id="EQ-999")
    assert r["total_count"] == 0
    assert len(r["warnings"]) == 1
    assert "EQ-999" in r["warnings"][0]


def test_ac06_잘림_표시():
    """AC-06: 기본 limit(200)보다 많으면 200건만 주고 truncated=True, 요약은 전체 기준"""
    r = query_downtime_logs()
    assert r["returned_count"] == 200
    assert r["truncated"] is True
    assert r["summary"]["record_count"] == 14099


def test_ac07_limit_범위():
    """AC-07: limit 이 너무 크면 1000 으로 맞춘다"""
    assert query_downtime_logs(limit=5000)["returned_count"] == 1000


def test_ac08_복합_조건():
    """AC-08: M-204 이면서 60분 이상 → 182건"""
    assert query_downtime_logs(error_code="M-204", min_downtime=60)["total_count"] == 182


# parametrize = 같은 시험을 입력만 바꿔서 여러 번 돌리는 기능
# 아래 시험은 잘못된 입력 3가지로 각각 한 번씩, 총 3번 실행된다
BAD_INPUTS = [
    {"date_from": "2026/08/10"},                             # 날짜 형식 오류
    {"date_from": "2026-08-11", "date_to": "2026-08-10"},    # 시작일이 종료일보다 늦음
    {"min_downtime": 10, "max_downtime": 5},                 # 최소가 최대보다 큼
]


@pytest.mark.parametrize("bad", BAD_INPUTS)
def test_ac09_입력_오류(bad):
    """AC-09: 함수는 ValueError, MCP 도구는 error/hint dict 를 돌려준다"""
    with pytest.raises(ValueError):
        query_downtime_logs(**bad)      # **bad = 사전의 내용을 이름=값 형태로 풀어서 넣기

    result = get_downtime_logs(**bad)
    assert "error" in result and "hint" in result
