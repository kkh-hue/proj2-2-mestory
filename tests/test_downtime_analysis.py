"""
다운타임 분석 화면 집계 로직 시험 (docs/specs/downtime-analysis.md 의 AC).

DB·CSV 없이 돌아가는 순수 함수 시험이라 모두 @pytest.mark.no_data.
"""

from datetime import date, datetime

import pytest

from backend.analysis import build_analysis, resolve_period

D1, D2 = date(2026, 9, 14), date(2026, 9, 20)
T = datetime(2026, 9, 18, 14, 32)


def _row(code, desc, minutes, count=1, category="전기"):
    return (code, desc, category, count, minutes, T)


@pytest.mark.no_data
def test_ac01_기간_기본값은_오늘_포함_최근_7일():
    assert resolve_period(None, None, date(2026, 9, 20)) == (date(2026, 9, 14), date(2026, 9, 20))


@pytest.mark.no_data
def test_ac06_미래_date_to는_오늘로_잘림():
    _, end = resolve_period(date(2026, 9, 1), date(2026, 11, 2), date(2026, 9, 20))
    assert end == date(2026, 9, 20)


@pytest.mark.no_data
def test_ac07_시작이_끝보다_늦으면_에러():
    with pytest.raises(ValueError):
        resolve_period(date(2026, 9, 20), date(2026, 9, 1), date(2026, 9, 20))


@pytest.mark.no_data
def test_ac02_원인_3개는_기타_없이_비중_계산():
    r = build_analysis([_row("E-1", "a", 10), _row("E-2", "b", 60), _row("E-3", "c", 30)], None, 0, D1, D2)
    assert [c["percent"] for c in r["causes"]] == [60.0, 30.0, 10.0]   # 시간 내림차순 정렬
    assert len(r["breakdown"]) == 3
    assert all(b["label"] != "기타" for b in r["breakdown"])
    assert r["total_downtime_min"] == 100.0


@pytest.mark.no_data
def test_ac03_원인_6개는_상위4_더하기_기타이고_합계_100():
    rows = [_row(f"E-{i}", f"cause{i}", m) for i, m in enumerate([50, 20, 10, 8, 7, 5])]
    r = build_analysis(rows, None, 0, D1, D2)
    assert len(r["breakdown"]) == 5
    assert r["breakdown"][-1] == {"label": "기타", "category": "기타", "percent": 12.0}
    assert sum(b["percent"] for b in r["breakdown"]) == pytest.approx(100, abs=0.1)


@pytest.mark.no_data
def test_ac05_사전에_없는_코드는_미등록으로_표시():
    r = build_analysis([_row("E-999", None, 5)], None, 1, D1, D2)
    assert r["causes"][0]["label"] == "E-999 (사전 미등록)"
    assert r["needs_review_count"] == 1


@pytest.mark.no_data
def test_ac08_기록이_없으면_빈_결과():
    r = build_analysis([], None, 0, D1, D2)
    assert r["event_count"] == 0
    assert r["total_downtime_min"] == 0
    assert r["top_equipment"] is None
    assert r["causes"] == [] and r["breakdown"] == []


@pytest.mark.no_data
def test_건수와_최대영향설비():
    r = build_analysis([_row("E-1", "a", 30, count=3), _row("E-2", "b", 10, count=2)],
                       ("EQ-021", "컨베이어", 25.0), 0, D1, D2)
    assert r["event_count"] == 5
    assert r["top_equipment"] == {"equipment_id": "EQ-021", "equipment_type": "컨베이어", "downtime_min": 25.0}
