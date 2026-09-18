import { IconChevronRight } from "./icons";
import type { DashboardEvent } from "../types/dashboard";
import type { Severity } from "../types/report";

const severityClass: Record<Severity, string> = {
  "중대": "severity-badge-critical",
  "보통": "severity-badge-warning",
  "경미": "severity-badge-ok",
  "판정 불가": "severity-badge-unknown",
};

function formatDateTime(iso: string | null) {
  if (!iso) return "-";
  const date = new Date(iso);
  return `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, "0")}.${String(date.getDate()).padStart(2, "0")} ${String(
    date.getHours(),
  ).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

export default function EventsTable({ rows, needsReviewCount }: { rows: DashboardEvent[]; needsReviewCount: number }) {
  return (
    <section className="events-card">
      <div className="events-head">
        <h3>최근 다운타임 이벤트</h3>
        {needsReviewCount > 0 && <span className="events-review-badge">분석이 필요한 이벤트 {needsReviewCount}건 ›</span>}
      </div>
      {rows.length === 0 ? (
        <p className="no-causes">최근 다운타임 기록이 없습니다.</p>
      ) : (
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
                <tr key={row.log_id}>
                  <td className="events-id">{row.equipment_id}</td>
                  <td>{row.equipment_type ?? "-"}</td>
                  <td>{row.line_id}</td>
                  <td>{formatDateTime(row.start_time)}</td>
                  <td>{formatDateTime(row.end_time)}</td>
                  <td>{row.downtime_min !== null ? `${Math.round(row.downtime_min)}분` : "-"}</td>
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
      )}
    </section>
  );
}
