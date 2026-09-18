import { IconCalendar, IconChart, IconClock, IconDownload, IconEye, IconMoreHorizontal, IconReport } from "./icons";
import type { ReportListItem } from "../lib/mockReports";

const ICON = { chart: IconChart, clock: IconClock, document: IconReport };

export default function ReportListCard({ report }: { report: ReportListItem }) {
  const Icon = ICON[report.icon];
  const complete = report.status === "complete";

  return (
    <article className="report-list-card">
      <div className={`report-list-icon ${report.iconTone === "solid" ? "report-list-icon-solid" : "report-list-icon-soft"}`}>
        <Icon />
      </div>
      <div className="report-list-body">
        <div className="report-list-top">
          <h4>{report.title}</h4>
          <div className="report-list-top-actions">
            <span className={`status-pill ${complete ? "status-pill-complete" : "status-pill-generating"}`}>
              {complete ? "분석 완료" : "생성 중"}
            </span>
            <button type="button" className="icon-button" aria-label="더보기">
              <IconMoreHorizontal />
            </button>
          </div>
        </div>
        <div className="report-list-meta">
          <span>
            <IconCalendar /> {report.date}
          </span>
          <span>
            <IconChart /> {report.line}
          </span>
          <span className="report-list-tag">{report.tag}</span>
        </div>
        <p className="report-list-desc">{report.description}</p>
        <div className="report-list-actions">
          <button type="button" className="secondary-button" disabled={!complete}>
            <IconEye /> 보기
          </button>
          <button type="button" className="primary-button primary-button-inline">
            <IconDownload /> 다운로드
          </button>
        </div>
      </div>
    </article>
  );
}
