export type TopDowntimeCode = { error_code: string; count: number; total_downtime_min: number; description: string | null };
export type ReportStatistics = {
  record_count: number;
  total_downtime_min: number;
  unplanned_downtime_min: number;
  code_summary_downtime_min: number;
  top_downtime_codes: TopDowntimeCode[];
};
