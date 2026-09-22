import pandas as pd
import pytest

from backend.services.report_statistics import calculate_statistics

pytestmark = pytest.mark.no_data


def sample_rows():
    return pd.DataFrame([
        {"start_time": "2026-08-01 10:00", "line_id": "LINE-A", "equipment_id": "EQ-1", "downtime_min": 30, "error_code": "E-1", "flags": []},
        {"start_time": "2026-08-02 10:00", "line_id": "LINE-A", "equipment_id": "EQ-1", "downtime_min": 20, "error_code": "E-1", "flags": []},
        {"start_time": "2026-08-03 10:00", "line_id": "LINE-A", "equipment_id": "EQ-1", "downtime_min": 50, "error_code": "E-2", "flags": []},
        {"start_time": "2026-08-04 10:00", "line_id": "LINE-A", "equipment_id": "EQ-1", "downtime_min": 40, "error_code": "ETC-602", "flags": []},
        {"start_time": "2026-08-05 10:00", "line_id": "LINE-A", "equipment_id": "EQ-2", "downtime_min": 99, "error_code": "E-9", "flags": []},
        {"start_time": "2026-08-06 10:00", "line_id": "LINE-A", "equipment_id": "EQ-1", "downtime_min": -5, "error_code": "E-3", "flags": ["NEGATIVE_DOWNTIME"]},
        {"start_time": "2026-08-07 10:00", "line_id": "LINE-A", "equipment_id": "EQ-1", "downtime_min": 80, "error_code": "E-4", "flags": ["UNREGISTERED_CODE"]},
    ])


def test_filters_and_kpis_and_top3():
    result = calculate_statistics(sample_rows(), date_from="2026-08-01", date_to="2026-08-04", line_id="line-a", equipment_id="eq-1")
    assert (result.record_count, result.total_downtime_min, result.unplanned_downtime_min) == (4, 140.0, 100.0)
    assert [(x.error_code, x.total_downtime_min) for x in result.top_downtime_codes] == [("E-1", 50.0), ("E-2", 50.0)]
    # TOP 3 비율의 분모는 계획 정지(ETC-602)를 빼고 코드 집계에 포함된 합계다.
    assert result.code_summary_downtime_min == 100.0


def test_excludes_negative_and_unregistered_from_code_top():
    result = calculate_statistics(sample_rows(), line_id="LINE-A", equipment_id="EQ-1")
    assert result.total_downtime_min == 220.0
    assert all(item.error_code != "E-4" for item in result.top_downtime_codes)
    assert result.code_summary_downtime_min == 100.0


def test_empty_filter_result():
    result = calculate_statistics(sample_rows(), equipment_id="EQ-404")
    assert result == calculate_statistics(sample_rows(), date_from="2027-01-01")
    assert result.record_count == 0 and result.top_downtime_codes == ()
