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
import { getReport, listEquipment } from "../../../lib/api";
import { reportScope, reportTitle } from "../../../lib/labels";
import type { EquipmentSummaryItem } from "../../../types/equipment";
import { downloadCsv } from "../../../lib/reportCsv";
import type { SavedReport } from "../../../types/report";

export default function ReportDetailPage({ params }: { params: { id: string } }) {
  const [report, setReport] = useState<SavedReport | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [equipment, setEquipment] = useState<EquipmentSummaryItem[]>([]);
  const [equipmentError, setEquipmentError] = useState("");

  useEffect(() => {
    listEquipment()
      .then(setEquipment)
      .catch((cause) => setEquipmentError(cause instanceof Error ? cause.message : "설비 목록을 불러오지 못했습니다."));
    getReport(params.id)
      .then(setReport)
      .catch((cause) => setError(cause instanceof Error ? cause.message : "리포트를 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, [params.id]);

  return (
    <main className="page">
      <Topbar
        title={report ? reportTitle(report, equipment) : "리포트 상세"}
        subtitle={report ? `${reportScope(report, equipment)} · ${report.period}` : "불러오는 중..."}
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

      {!loading && (error || equipmentError) && (
        <section className="status-card status-error" role="alert">
          <strong>리포트를 불러오지 못했습니다.</strong>
          <span>{error || equipmentError}</span>
        </section>
      )}

      {!loading && !error && report && (
        <>
          {equipmentError && (
            <p className="form-error" role="status">
              설비 정보를 불러오지 못했습니다. {equipmentError}
            </p>
          )}
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
