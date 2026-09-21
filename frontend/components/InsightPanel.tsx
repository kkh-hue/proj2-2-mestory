import { IconAlertCircle, IconCheck, IconReport } from "./icons";
import type { DowntimeReport } from "../types/report";

export default function InsightPanel({ report }: { report: DowntimeReport }) {
  const confirmedCount = report.causes.filter((c) => c.is_confirmed).length;

  const stats = [
    { icon: IconReport, label: "분석된 원인", value: `${report.causes.length}건`, note: "이번 조회 조건에서 확인된 원인 수입니다." },
    { icon: IconCheck, label: "확정 원인", value: `${confirmedCount}건`, note: `잠정 판단 ${report.causes.length - confirmedCount}건 포함 전체 ${report.causes.length}건 중.` },
    { icon: IconAlertCircle, label: "확인 필요", value: `${report.unclassified_count}건`, note: "미등록 코드·데이터 오류 등 판정 불가 건수입니다." },
  ];

  return (
    <section className="insight-panel">
      <div className="card-head">
        <h3>분석 인사이트</h3>
      </div>
      <ul className="insight-list">
        {stats.map(({ icon: Icon, label, value, note }) => (
          <li key={label}>
            <span className="insight-icon">
              <Icon />
            </span>
            <div>
              <span className="insight-label">{label}</span>
              <div className="insight-value">{value}</div>
              <p className="insight-note">{note}</p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
