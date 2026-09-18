// 리포트 상세 (F-07) — AI 원인분석 화면의 "상세 리포트 보기"가 여기로 온다.
// 엑셀 다운로드는 의존성 추가 없이 CSV로 만든다 (엑셀이 CSV를 그대로 열 수 있고,
// xlsx 패키지는 npm 배포판에 고쳐지지 않은 취약점이 있어 쓰지 않는다).
// PDF 다운로드는 브라우저 인쇄(다른 프린터로 저장 → PDF)로 처리한다 — 별도 서버 렌더링 없이 바로 된다.
"use client";

import { useEffect, useState } from "react";
import CauseBreakdown from "../../../components/CauseBreakdown";
import CauseDetailTable from "../../../components/CauseDetailTable";
import InsightPanel from "../../../components/InsightPanel";
import Topbar from "../../../components/Topbar";
import { IconDownload, IconReport } from "../../../components/icons";
import { getReport } from "../../../lib/api";
import type { SavedReport } from "../../../types/report";

function csvCell(value: string): string {
  return `"${value.replace(/"/g, '""')}"`;
}

function toCsv(report: SavedReport): string {
  const rows = [
    ["항목", "값"],
    ["리포트 ID", report.id],
    ["생성 시각", report.created_at],
    ["기간", report.period],
    ["라인", report.line_id],
    ["설비", report.equipment_id],
    ["확인 필요 건수", String(report.unclassified_count)],
    ["권장 조치", report.recommended_action],
    ["분석 참고 사항", report.confidence_note],
    [],
    ["에러코드", "설명", "심각도", "확정 여부", "판단 근거"],
    ...report.causes.map((cause) => [
      cause.error_code, cause.description, cause.severity,
      cause.is_confirmed ? "확정" : "확인 필요", cause.evidence,
    ]),
  ];
  return rows.map((row) => row.map(csvCell).join(",")).join("\r\n");
}

function downloadCsv(report: SavedReport) {
  // BOM(﻿)을 앞에 붙여야 엑셀이 한글을 깨진 글자 없이 연다.
  const blob = new Blob([`﻿${toCsv(report)}`], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `mestory-report-${report.id}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

export default function ReportDetailPage({ params }: { params: { id: string } }) {
  const [report, setReport] = useState<SavedReport | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getReport(params.id)
      .then(setReport)
      .catch((cause) => setError(cause instanceof Error ? cause.message : "리포트를 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, [params.id]);

  return (
    <main className="page">
      <Topbar
        title="리포트 상세"
        subtitle={report ? `${report.line_id} · ${report.equipment_id} · ${report.period}` : "불러오는 중..."}
        action={
          report ? (
            <>
              <button type="button" className="secondary-button no-print" onClick={() => downloadCsv(report)}>
                <IconDownload /> 엑셀 다운로드
              </button>
              <button type="button" className="primary-button-inline no-print" onClick={() => window.print()}>
                <IconReport /> PDF로 저장
              </button>
            </>
          ) : undefined
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

      {!loading && !error && report && (
        <>
          <div className="dashboard-grid">
            <CauseBreakdown causes={report.causes} />
            <InsightPanel report={report} />
          </div>
          <CauseDetailTable causes={report.causes} />
          <section className="recommendation-panel">
            <h3>권장 조치</h3>
            <p>{report.recommended_action}</p>
          </section>
          <section className="note-panel">
            <h3>분석 참고 사항</h3>
            <p>{report.confidence_note}</p>
          </section>
        </>
      )}
    </main>
  );
}
