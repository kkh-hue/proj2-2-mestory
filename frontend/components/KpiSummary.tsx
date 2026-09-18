export type KpiSummaryData = {
  record_count: number;
  total_downtime_min: number;
  unplanned_downtime_min: number;
};

/** 실제 집계 결과만 표시한다. 비교 기준이 없는 증감 수치는 추가하지 않는다. */
export default function KpiSummary({ data }: { data: KpiSummaryData }) {
  return <section aria-label="KPI 요약" className="kpi-summary">
    <div><span>총 다운타임</span><strong>{data.total_downtime_min.toLocaleString()}분</strong></div>
    <div><span>다운타임 발생 건수</span><strong>{data.record_count.toLocaleString()}건</strong></div>
    <div><span>비계획 다운타임</span><strong>{data.unplanned_downtime_min.toLocaleString()}분</strong></div>
  </section>;
}
