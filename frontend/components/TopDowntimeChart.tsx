export type TopDowntimeCode = {
  error_code: string;
  count: number;
  total_downtime_min: number;
  /** 오류 코드 사전에서 조회한 공식 설명이 있을 때만 전달한다. */
  description?: string | null;
};

type Props = {
  items: TopDowntimeCode[];
  /** 계획 정지와 코드 집계 제외 flag를 뺀 동일 기준의 전체 합계. */
  codeSummaryDowntimeMin?: number;
};

export default function TopDowntimeChart({ items, codeSummaryDowntimeMin }: Props) {
  const topItems = items.slice(0, 3);
  const canShowShare = typeof codeSummaryDowntimeMin === "number" && codeSummaryDowntimeMin > 0;

  return <section aria-label="주요 다운타임 TOP 3" className="top-downtime-chart">
    <h3>주요 다운타임 TOP 3</h3>
    {topItems.length === 0 ? <p>해당 조건의 집계 항목이 없습니다.</p> : <ol>{topItems.map((item, index) => {
      const share = canShowShare ? (item.total_downtime_min / codeSummaryDowntimeMin) * 100 : null;
      return <li key={item.error_code}>
        <span className="rank">{index + 1}</span><div className="top-content"><b>{item.error_code}</b>{item.description && <span className="description">{item.description}</span>}</div>
        <span className="metric">{item.total_downtime_min.toLocaleString()}분{share !== null && ` · ${share.toFixed(1)}%`}</span>
      </li>;
    })}</ol>}
    <style jsx>{`
      .top-downtime-chart{padding:18px;border:1px solid #dce6eb;border-radius:10px;background:#fff}h3{margin:0 0 14px}ol{display:grid;gap:14px;margin:0;padding:0;list-style:none}li{display:grid;grid-template-columns:24px minmax(0,1fr) auto;align-items:center;gap:10px}.rank{color:#5f579e;font-weight:800}.top-content{min-width:0}b{margin-right:8px}.description{color:#64748b;font-size:13px}.metric{color:#475569;font-size:13px;white-space:nowrap}@media(max-width:560px){li{grid-template-columns:24px minmax(0,1fr)}.metric{grid-column:2}}
    `}</style>
  </section>;
}
