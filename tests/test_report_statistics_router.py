import pytest

fastapi = pytest.importorskip("fastapi")

from backend.routers import report_statistics
from backend.services.report_statistics import ReportStatistics, TopDowntimeCode


def test_router_uses_statistics_and_official_descriptions(monkeypatch):
    monkeypatch.setattr(report_statistics, "calculate_report_statistics", lambda **_: ReportStatistics(
        record_count=2, total_downtime_min=30.0, unplanned_downtime_min=30.0,
        top_downtime_codes=(TopDowntimeCode("E-100", 2, 30.0),), code_summary_downtime_min=30.0,
    ))
    monkeypatch.setattr(report_statistics, "get_official_descriptions", lambda _: {"E-100": "official"})
    response = report_statistics.create_report_statistics(report_statistics.ReportStatisticsRequest(line_id="LINE-A"))
    assert response.top_downtime_codes[0].description == "official"
    assert response.code_summary_downtime_min == 30.0
