// backend GET /dashboard 응답 (backend/db.py get_dashboard_summary). 대시보드 화면용.
import type { SavedReport, Severity } from "./report";

export interface KpiDelta {
  direction: "up" | "down";
  percent: number;
}

export interface DashboardKpi {
  today_downtime_min: number;
  avg_recovery_min: number;
  reports_today: number;
  equipment_count: number;
  utilization_pct: number;
  downtime_delta: KpiDelta;
  recovery_delta: KpiDelta;
  reports_delta: KpiDelta;
  utilization_delta: KpiDelta;
}

export interface DashboardTrendLine {
  key: string;
  values: number[];
}

export interface DashboardTrend {
  labels: string[]; // YYYY-MM-DD
  lines: DashboardTrendLine[];
}

export interface DashboardEvent {
  log_id: string;
  equipment_id: string;
  equipment_type: string | null;
  line_id: string;
  start_time: string;
  end_time: string | null;
  downtime_min: number | null;
  status: "복구 완료" | "진행 중";
  severity: Severity;
  cause: string;
}

export interface DashboardSummary {
  kpi: DashboardKpi;
  trend: DashboardTrend;
  recent_events: DashboardEvent[];
  latest_report: SavedReport | null;
}
