import { IconChevronRight } from "./icons";
import type { DowntimeEventRow } from "../lib/mockDashboard";

const severityClass: Record<DowntimeEventRow["severity"], string> = {
  긴급: "severity-badge-critical",
  주의: "severity-badge-warning",
  정상: "severity-badge-ok",
};

export default function EventsTable({ rows, needsReviewCount }: { rows: DowntimeEventRow[]; needsReviewCount: number }) {
  return (
    <section className="events-card">
      <div className="events-head">
        <h3>최근 다운타임 이벤트</h3>
        {needsReviewCount > 0 && <span className="events-review-badge">분석이 필요한 이벤트 {needsReviewCount}건 ›</span>}
      </div>
      <div className="events-table-wrap">
        <table className="events-table">
          <thead>
            <tr>
              <th>설비 ID</th>
              <th>설비명</th>
              <th>라인</th>
              <th>발생 시간</th>
              <th>복구 시간</th>
              <th>지속 시간</th>
              <th>심각도</th>
              <th>상태</th>
              <th>원인 (AI 분석)</th>
              <th aria-hidden="true" />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.equipmentId}>
                <td className="events-id">{row.equipmentId}</td>
                <td>{row.equipmentName}</td>
                <td>{row.line}</td>
                <td>{row.occurredAt}</td>
                <td>{row.recoveredAt}</td>
                <td>{row.durationMin}분</td>
                <td>
                  <span className={`severity-badge ${severityClass[row.severity]}`}>{row.severity}</span>
                </td>
                <td>
                  <span className="status-badge">{row.status}</span>
                </td>
                <td>{row.cause}</td>
                <td>
                  <IconChevronRight className="events-row-chevron" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
