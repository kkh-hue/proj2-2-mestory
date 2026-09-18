import Link from "next/link";
import { IconCalendar, IconChart, IconDownload, IconEye, IconMoreHorizontal, IconReport } from "./icons";
import type { ReportSummary } from "../types/report";

function formatDate(iso: string) {
  const date = new Date(iso);
  return `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, "0")}.${String(date.getDate()).padStart(2, "0")} ${String(
    date.getHours(),
  ).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

export default function ReportListCard({ report, highlight }: { report: ReportSummary; highlight?: boolean }) {
  const detailHref = `/reports/${report.id}`;

  return (
    <article className="report-list-card">
      <div className={`report-list-icon ${highlight ? "report-list-icon-solid" : "report-list-icon-soft"}`}>
        <IconReport />
      </div>
      <div className="report-list-body">
        <div className="report-list-top">
          <h4>{report.line_id} · {report.equipment_id} 원인 분석 리포트</h4>
          <div className="report-list-top-actions">
            <span className="status-pill status-pill-complete">분석 완료</span>
            <button type="button" className="icon-button" aria-label="더보기">
              <IconMoreHorizontal />
            </button>
          </div>
        </div>
        <div className="report-list-meta">
          <span>
            <IconCalendar /> {formatDate(report.created_at)}
          </span>
          <span>
            <IconChart /> {report.line_id}
          </span>
          <span className="report-list-tag">{report.equipment_id}</span>
        </div>
        <p className="report-list-desc">{report.recommended_action}</p>
        <div className="report-list-actions">
          <Link href={detailHref} className="secondary-button">
            <IconEye /> 보기
          </Link>
          <Link href={detailHref} className="primary-button primary-button-inline">
            <IconDownload /> 다운로드
          </Link>
        </div>
      </div>
    </article>
  );
}
