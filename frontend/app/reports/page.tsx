// 리포트 (F-07) — backend GET /reports를 그대로 불러온다.
// "최근 공유된 리포트"는 공유·계정 기능이 없어서 지어낼 수 없었다 —
// 대신 같은 실제 데이터에서 최근 5건만 보여주는 목록으로 바꿨다.
"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import ReportListCard from "../../components/ReportListCard";
import Topbar from "../../components/Topbar";
import { IconChevronDown, IconChevronRight, IconPlus, IconReport, IconSearch } from "../../components/icons";
import { listEquipment, listReports, ReportApiError } from "../../lib/api";
import { reportScope } from "../../lib/labels";
import type { EquipmentSummaryItem } from "../../types/equipment";
import type { ReportSummary } from "../../types/report";

function formatShortDate(iso: string) {
  const date = new Date(iso);
  return `${date.getMonth() + 1}.${date.getDate()} ${String(date.getHours()).padStart(2, "0")}:${String(
    date.getMinutes(),
  ).padStart(2, "0")}`;
}

function reportsErrorMessage(cause: unknown): string {
  if (cause instanceof ReportApiError) {
    return "리포트를 불러오지 못했습니다.\n다시 시도해 주세요.";
  }
  if (cause instanceof Error && cause.message.includes("10초")) {
    return "리포트를 불러오지 못했습니다.\n다시 시도해 주세요.";
  }
  return "네트워크 연결을 확인해 주세요.";
}

export default function ReportsPage() {
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [equipment, setEquipment] = useState<EquipmentSummaryItem[]>([]);
  const [equipmentError, setEquipmentError] = useState("");

  useEffect(() => {
    listEquipment()
      .then(setEquipment)
      .catch((cause) => setEquipmentError(reportsErrorMessage(cause)));
    listReports()
      .then(setReports)
      .catch((cause) => setError(reportsErrorMessage(cause)))
      .finally(() => setLoading(false));
  }, []);

  const [query, setQuery] = useState("");
  const [newestFirst, setNewestFirst] = useState(true);

  const recent = reports.slice(0, 5);
  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = q
      ? reports.filter((r) =>
          [r.line_id, r.equipment_id, reportScope(r, equipment), r.recommended_action, r.period].some((v) => v?.toLowerCase().includes(q)),
        )
      : reports;
    return newestFirst ? filtered : [...filtered].reverse();
  }, [reports, query, newestFirst, equipment]);

  return (
    <main className="page">
      <Topbar
        title="리포트"
        subtitle="AI 원인분석이 생성한 리포트를 확인하세요."
        action={
          <>
            <label className="search-box">
              <IconSearch />
              <input type="text" placeholder="리포트 검색" aria-label="리포트 검색" value={query} onChange={(e) => setQuery(e.target.value)} />
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
      {!loading && (error || equipmentError) && (
        <section className="status-card status-error" role="alert">
          <span style={{ whiteSpace: "pre-line" }}>{error || equipmentError}</span>
        </section>
      )}

      {!loading && !error && !equipmentError && (
        <div className="reports-grid">
          <section>
            <div className="reports-list-head">
              <h3>전체 리포트 ({visible.length})</h3>
              <button type="button" className="sort-select" onClick={() => setNewestFirst((v) => !v)} aria-label="정렬 순서 바꾸기">
                {newestFirst ? "최신순" : "오래된순"}
                <IconChevronDown className="filter-chevron" />
              </button>
            </div>
            {reports.length === 0 ? (
              <p className="no-causes">
                아직 생성된 리포트가 없습니다. "AI 원인분석" 화면에서 질문하면 여기에 쌓입니다.
              </p>
            ) : visible.length === 0 ? (
              <p className="no-causes">검색 결과가 없습니다.</p>
            ) : (
              <div className="report-list">
                {visible.map((report, index) => (
                  <ReportListCard report={report} highlight={index === 0} equipment={equipment} key={report.id} />
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
                      <span className="shared-report-name">{reportScope(report, equipment)}</span>
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
