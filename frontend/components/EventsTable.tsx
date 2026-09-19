import { useRouter } from "next/navigation";
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
  const router = useRouter();

  // 개별 다운타임 기록 상세 화면은 아직 없다(backend/db.py의 lateral join 주석 참고 —
  // 붙어 있는 원인도 "같은 설비의 가장 최근 리포트"일 뿐 이 사건의 리포트라는 보장이
  // 없다). 그래서 AlertRow와 같은 규칙으로 설비관리 화면으로 보낸다.
  function goToEquipment() {
    router.push("/equipment");
  }

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
                <tr
                  key={row.log_id}
                  className="events-row-clickable"
                  role="button"
                  tabIndex={0}
                  onClick={goToEquipment}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      goToEquipment();
                    }
                  }}
                >
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
