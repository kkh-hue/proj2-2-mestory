// 리포트 (F-07) — backend GET /reports를 그대로 불러온다.
// "최근 공유된 리포트"는 공유·계정 기능이 없어서 지어낼 수 없었다 —
// 대신 같은 실제 데이터에서 최근 5건만 보여주는 목록으로 바꿨다.
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import ReportListCard from "../../components/ReportListCard";
import Topbar from "../../components/Topbar";
import { IconChevronDown, IconChevronRight, IconPlus, IconReport, IconSearch } from "../../components/icons";
import { listReports } from "../../lib/api";
import type { ReportSummary } from "../../types/report";

function formatShortDate(iso: string) {
  const date = new Date(iso);
  return `${date.getMonth() + 1}.${date.getDate()} ${String(date.getHours()).padStart(2, "0")}:${String(
    date.getMinutes(),
  ).padStart(2, "0")}`;
}

export default function ReportsPage() {
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    listReports()
      .then(setReports)
      .catch((cause) => setError(cause instanceof Error ? cause.message : "리포트를 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, []);

  const recent = reports.slice(0, 5);

  return (
    <main className="page">
      <Topbar
        title="리포트"
        subtitle="AI 원인분석이 생성한 리포트를 확인하세요."
        action={
          <>
            <label className="search-box">
              <IconSearch />
              <input type="text" placeholder="리포트 검색" aria-label="리포트 검색" />
            </label>
            <Link href="/downtime/ai" className="new-analysis-button">
              <IconPlus />
              새 리포트 생성
            </Link>
          </>
        }
      />

      {loading && (
        <section className="status-card status-loading" aria-live="polite">
          <span className="spinner" /> 리포트를 불러오는 중입니다.
        </section>
      )}
      {!loading && error && (
        <section className="status-card status-error" role="alert">
          <strong>리포트를 불러오지 못했습니다.</strong>
          <span>{error}</span>
        </section>
      )}

      {!loading && !error && (
        <div className="reports-grid">
          <section>
            <div className="reports-list-head">
              <h3>전체 리포트 ({reports.length})</h3>
              <span className="sort-select">
                최신순
                <IconChevronDown className="filter-chevron" />
              </span>
            </div>
            {reports.length === 0 ? (
              <p className="no-causes">
                아직 생성된 리포트가 없습니다. "AI 원인분석" 화면에서 질문하면 여기에 쌓입니다.
              </p>
            ) : (
              <div className="report-list">
                {reports.map((report, index) => (
                  <ReportListCard report={report} highlight={index === 0} key={report.id} />
                ))}
              </div>
            )}
          </section>

          <section className="shared-reports-card">
            <div className="reports-list-head">
              <h3>최근 생성된 리포트</h3>
            </div>
            {recent.length === 0 ? (
              <p className="helper-text">아직 없습니다.</p>
            ) : (
              <ul className="shared-report-list">
                {recent.map((report) => (
                  <li key={report.id}>
                    <span className="shared-avatar shared-avatar-purple">
                      <IconReport />
                    </span>
                    <div className="shared-report-body">
                      <span className="shared-report-name">{report.line_id} · {report.equipment_id}</span>
                      <span className="shared-report-title">{report.recommended_action}</span>
                      <span className="shared-report-date">{formatShortDate(report.created_at)}</span>
                    </div>
                    <Link href={`/reports/${report.id}`} aria-label="상세 보기">
                      <IconChevronRight className="events-row-chevron" />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </main>
  );
}
