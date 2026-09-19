// 실제 분석 실행 화면 — 조건 입력 후 backend POST /report를 호출한다 (PRD F-07).
// 원인별 분석/인사이트/상세 테이블은 전부 실제 DowntimeReport 응답 값만 사용한다 —
// 출력 계약에 없는 수치(발생 건수·총 시간 등)는 화면에서도 지어내지 않는다.
// "다운타임 분석"(/downtime)은 디자인 목업이라 이 화면을 별도 경로로 분리했다 — "분석 실행" 버튼에서 진입.
"use client";

import { FormEvent, useState } from "react";
import CauseBreakdown from "../../../components/CauseBreakdown";
import CauseDetailTable from "../../../components/CauseDetailTable";
import FilterCard from "../../../components/FilterCard";
import InsightPanel from "../../../components/InsightPanel";
import Topbar from "../../../components/Topbar";
import { IconCalendar, IconEquipment, IconChart as IconLine, IconPlus } from "../../../components/icons";
import { createReport } from "../../../lib/api";
import type { DowntimeReport, ReportRequest } from "../../../types/report";

function makeSessionId() {
  return typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `session-${Date.now()}`;
}

const today = new Date().toISOString().slice(0, 10);

export default function DowntimeAnalysisRunPage() {
  const [sessionId] = useState(makeSessionId);
  const [dateFrom, setDateFrom] = useState(today);
  const [dateTo, setDateTo] = useState(today);
  const [lineId, setLineId] = useState("");
  const [equipmentId, setEquipmentId] = useState("");
  const [validationError, setValidationError] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<DowntimeReport | null>(null);

  async function runAnalysis(event: FormEvent) {
    event.preventDefault();
    if (dateFrom && dateTo && dateFrom > dateTo) {
      setValidationError("시작일은 종료일보다 늦을 수 없습니다.");
      return;
    }
    setValidationError("");

    const request: Omit<ReportRequest, "session_id"> = {
      date_from: dateFrom || null,
      date_to: dateTo || null,
      line_id: lineId.trim() || null,
      equipment_id: equipmentId.trim() || null,
    };

    setLoading(true);
    setError("");
    try {
      setResult(await createReport({ ...request, session_id: sessionId }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "알 수 없는 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page">
      <Topbar
        title="분석 실행"
        subtitle="조건을 입력하면 실제 원인 분석 리포트를 생성합니다. 아래에서 조회 기간을 직접 고를 수 있습니다."
        action={
          <button type="submit" form="analysis-filters" className="new-analysis-button" disabled={loading}>
            <IconPlus />
            {loading ? "분석 중..." : "분석 실행"}
          </button>
        }
      />

      <form id="analysis-filters" className="filter-row" onSubmit={runAnalysis}>
        <FilterCard icon={<IconCalendar />} label="기간">
          <div className="filter-date-range">
            <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} aria-label="조회 시작일" />
            <span>~</span>
            <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} aria-label="조회 종료일" />
          </div>
        </FilterCard>
        <FilterCard icon={<IconLine />} label="라인">
          <input placeholder="전체 라인" value={lineId} onChange={(e) => setLineId(e.target.value)} aria-label="라인 ID" />
        </FilterCard>
        <FilterCard icon={<IconEquipment />} label="설비">
          <input placeholder="전체 설비" value={equipmentId} onChange={(e) => setEquipmentId(e.target.value)} aria-label="설비 ID" />
        </FilterCard>
      </form>
      {validationError && <p className="form-error" role="alert">{validationError}</p>}

      {loading && (
        <section className="status-card status-loading" aria-live="polite">
          <span className="spinner" /> 분석 중입니다. 로그와 근거 데이터를 확인하고 있습니다.
        </section>
      )}

      {!loading && error && (
        <section className="status-card status-error" role="alert">
          <strong>분석을 완료하지 못했습니다.</strong>
          <span>{error}</span>
        </section>
      )}

      {!loading && !error && !result && (
        <section className="status-card status-empty">
          <strong>아직 분석 결과가 없습니다.</strong>
          <span>조건을 확인하고 "분석 실행"을 누르면 결과가 여기에 표시됩니다.</span>
        </section>
      )}

      {!loading && !error && result && (
        <>
          <div className="dashboard-grid">
            <CauseBreakdown causes={result.causes} />
            <InsightPanel report={result} />
          </div>
          <CauseDetailTable causes={result.causes} />
          <section className="recommendation-panel">
            <h3>권장 조치</h3>
            <p>{result.recommended_action}</p>
          </section>
          <section className="note-panel">
            <h3>분석 참고 사항</h3>
            <p>{result.confidence_note}</p>
          </section>
        </>
      )}
    </main>
  );
}
