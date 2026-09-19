// backend GET /downtime/analysis 응답 (backend/analysis.py build_analysis). 다운타임 분석 화면용.
export type AnalysisStatus = "all" | "closed" | "open";

export interface DowntimeAnalysisQuery {
  date_from: string;
  date_to: string;
  line_id?: string;
  equipment_id?: string;
  status: AnalysisStatus;
}

export interface AnalysisBreakdownItem {
  label: string;
  category: string;
  percent: number;
}

export interface AnalysisCause {
  error_code: string;
  label: string;
  category: string;
  count: number;
  downtime_min: number;
  percent: number;
  last_occurred: string | null;
}

export interface DowntimeAnalysis {
  date_from: string;
  date_to: string;
  event_count: number;
  total_downtime_min: number;
  top_equipment: { equipment_id: string; equipment_type: string | null; downtime_min: number } | null;
  needs_review_count: number;
  breakdown: AnalysisBreakdownItem[];
  causes: AnalysisCause[];
}
