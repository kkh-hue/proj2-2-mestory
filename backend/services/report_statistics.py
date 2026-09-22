"""독립적인 로그 통계 계산 모듈.

기존 MCP나 /report에 연결하지 않고 KPI/TOP 3 계산만 검증하기 위한 모듈이다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

PLANNED_STOP_CODES = {"ETC-602"}
EXCLUDE_FROM_CODE_SUMMARY = {"NEGATIVE_DOWNTIME", "EMPTY_ERROR_CODE", "UNREGISTERED_CODE"}


@dataclass(frozen=True)
class TopDowntimeCode:
    error_code: str
    count: int
    total_downtime_min: float
    description: str | None = None


@dataclass(frozen=True)
class ReportStatistics:
    record_count: int
    total_downtime_min: float
    unplanned_downtime_min: float
    top_downtime_codes: tuple[TopDowntimeCode, ...]
    code_summary_downtime_min: float = 0.0


def calculate_statistics(
    rows: pd.DataFrame,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    line_id: str | None = None,
    equipment_id: str | None = None,
) -> ReportStatistics:
    """조건에 맞는 rows에서 기존 MCP 요약 의미의 KPI/TOP 3를 계산한다."""
    frame = rows.copy()
    frame["_start_dt"] = pd.to_datetime(frame["start_time"])
    mask = pd.Series(True, index=frame.index)
    if date_from:
        mask &= frame["_start_dt"].dt.date >= pd.Timestamp(date_from).date()
    if date_to:
        mask &= frame["_start_dt"].dt.date <= pd.Timestamp(date_to).date()
    if line_id:
        mask &= frame["line_id"] == line_id.strip().upper()
    if equipment_id:
        mask &= frame["equipment_id"] == equipment_id.strip().upper()

    matched = frame[mask].copy()
    if matched.empty:
        return ReportStatistics(0, 0.0, 0.0, ())

    matched["downtime_min"] = matched["downtime_min"].astype(float)
    def excluded(flags: Any) -> bool:
        return bool(set(flags or []) & EXCLUDE_FROM_CODE_SUMMARY)

    # MCP summary excludes negative values by the NEGATIVE_DOWNTIME flag.
    countable = matched[~matched["flags"].map(lambda flags: "NEGATIVE_DOWNTIME" in (flags or []))]
    total = float(countable["downtime_min"].sum())
    planned = countable["error_code"].str.strip().isin(PLANNED_STOP_CODES)
    unplanned = total - float(countable.loc[planned, "downtime_min"].sum())

    code_rows = matched[~matched["error_code"].str.strip().isin(PLANNED_STOP_CODES)].copy()
    code_rows = code_rows[~code_rows["flags"].map(excluded)]
    grouped = (code_rows.groupby("error_code")["downtime_min"]
               .agg(count="count", total_downtime_min="sum")
               .reset_index()
               .sort_values(["total_downtime_min", "error_code"], ascending=[False, True], kind="stable")
               .head(3))
    code_summary_total = float(code_rows["downtime_min"].sum())
    top = tuple(TopDowntimeCode(str(row.error_code), int(row[1]), round(float(row[2]), 1))
                for row in grouped.itertuples(index=False))
    return ReportStatistics(len(matched), round(total, 1), round(unplanned, 1), top, round(code_summary_total, 1))


def calculate_report_statistics(*, date_from=None, date_to=None, line_id=None, equipment_id=None) -> ReportStatistics:
    """Calculate statistics through the existing MCP query and its summary rules."""
    from mcp_server.tools.downtime import query_downtime_logs

    summary = query_downtime_logs(date_from=date_from, date_to=date_to, line_id=line_id, equipment_id=equipment_id, limit=1)["summary"]
    by_code = summary.get("by_error_code", [])
    top = tuple(TopDowntimeCode(str(item["error_code"]), int(item["count"]), float(item["total_downtime_min"])) for item in by_code[:3])
    code_summary_total = sum(float(item["total_downtime_min"]) for item in by_code)
    return ReportStatistics(int(summary["record_count"]), float(summary["total_downtime_min"]), float(summary["unplanned_downtime_min"]), top, round(code_summary_total, 1))
