import Link from "next/link";
import { useState } from "react";
import { getReport } from "../lib/api";
import { reportScope, reportTitle } from "../lib/labels";
import type { EquipmentSummaryItem } from "../types/equipment";
import { downloadCsv } from "../lib/reportCsv";
import { IconCalendar, IconChart, IconDownload, IconEye, IconReport } from "./icons";
import type { ReportSummary } from "../types/report";

function formatDate(iso: string) {
  const date = new Date(iso);
  return `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, "0")}.${String(date.getDate()).padStart(2, "0")} ${String(
    date.getHours(),
  ).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

export default function ReportListCard({
  report,
  highlight,
  equipment,
}: {
  report: ReportSummary;
  highlight?: boolean;
  equipment: EquipmentSummaryItem[];
}) {
  const detailHref = `/reports/${report.id}`;
  const [downloading, setDownloading] = useState(false);

  // 목록 응답에는 causes가 없어서 상세를 받아 CSV로 저장한다.
  async function download() {
    setDownloading(true);
    try {
      downloadCsv(await getReport(report.id));
    } catch {
      window.alert("리포트를 다운로드하지 못했습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <article className="report-list-card">
      <div className={`report-list-icon ${highlight ? "report-list-icon-solid" : "report-list-icon-soft"}`}>
        <IconReport />
      </div>
      <div className="report-list-body">
        <div className="report-list-top">
          <h4>{reportTitle(report, equipment)}</h4>
          <div className="report-list-top-actions">
            <span className="status-pill status-pill-complete">분석 완료</span>
          </div>
        </div>
        <div className="report-list-meta">
          <span>
            <IconCalendar /> {formatDate(report.created_at)}
          </span>
          <span>
            <IconChart /> {reportScope(report, equipment)}
          </span>
          <span className="report-list-tag">{report.period}</span>
        </div>
        <p className="report-list-desc">{report.recommended_action}</p>
        <div className="report-list-actions">
          <Link href={detailHref} className="secondary-button">
            <IconEye /> 보기
          </Link>
          <button type="button" className="primary-button primary-button-inline" onClick={download} disabled={downloading}>
            <IconDownload /> {downloading ? "준비 중..." : "다운로드"}
          </button>
        </div>
      </div>
    </article>
  );
}
