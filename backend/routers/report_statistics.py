"""통계 endpoint 준비용 router. backend.main에는 아직 등록하지 않는다."""

from fastapi import APIRouter
from pydantic import BaseModel

from backend.services.error_code_adapter import get_official_descriptions
from backend.services.report_statistics import calculate_report_statistics

router = APIRouter(tags=["report"])


class ReportStatisticsRequest(BaseModel):
    date_from: str | None = None
    date_to: str | None = None
    line_id: str | None = None
    equipment_id: str | None = None


class TopDowntimeCodeResponse(BaseModel):
    error_code: str
    count: int
    total_downtime_min: float
    description: str | None = None


class ReportStatisticsResponse(BaseModel):
    record_count: int
    total_downtime_min: float
    unplanned_downtime_min: float
    code_summary_downtime_min: float
    top_downtime_codes: list[TopDowntimeCodeResponse]


@router.post("/report/statistics", response_model=ReportStatisticsResponse)
def create_report_statistics(request: ReportStatisticsRequest) -> ReportStatisticsResponse:
    stats = calculate_report_statistics(
        date_from=request.date_from,
        date_to=request.date_to,
        line_id=request.line_id,
        equipment_id=request.equipment_id,
    )
    descriptions = get_official_descriptions([item.error_code for item in stats.top_downtime_codes])
    return ReportStatisticsResponse(
        record_count=stats.record_count,
        total_downtime_min=stats.total_downtime_min,
        unplanned_downtime_min=stats.unplanned_downtime_min,
        code_summary_downtime_min=stats.code_summary_downtime_min,
        top_downtime_codes=[
            TopDowntimeCodeResponse(
                error_code=item.error_code,
                count=item.count,
                total_downtime_min=item.total_downtime_min,
                description=descriptions.get(item.error_code),
            )
            for item in stats.top_downtime_codes
        ],
    )
