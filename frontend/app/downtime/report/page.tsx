// 실제 분석 실행 화면 — 조건 입력 후 backend POST /report를 호출한다 (PRD F-07).
// 원인별 분석/인사이트/상세 테이블은 전부 실제 DowntimeReport 응답 값만 사용한다 —
// 출력 계약에 없는 수치(발생 건수·총 시간 등)는 화면에서도 지어내지 않는다.
// "다운타임 분석"(/downtime)은 디자인 목업이라 이 화면을 별도 경로로 분리했다 — "분석 실행" 버튼에서 진입.
"use client";

import { useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useMemo, useRef, useState } from "react";
import CauseBreakdown from "../../../components/CauseBreakdown";
import CauseDetailTable from "../../../components/CauseDetailTable";
import DateField from "../../../components/DateField";
import FilterCard from "../../../components/FilterCard";
import InsightPanel from "../../../components/InsightPanel";
import Topbar from "../../../components/Topbar";
import { IconCalendar, IconEquipment, IconChart as IconLine, IconPlus } from "../../../components/icons";
import { createReport, listEquipment } from "../../../lib/api";
import { todayKst } from "../../../lib/date";
import { equipmentLabel, lineLabel } from "../../../lib/labels";
import type { EquipmentSummaryItem } from "../../../types/equipment";
import type { DowntimeReport, ReportRequest } from "../../../types/report";

function makeSessionId() {
  return typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `session-${Date.now()}`;
}

const today = todayKst();

export default function DowntimeAnalysisRunPage() {
  // useSearchParams는 Suspense 경계가 없으면 프로덕션 빌드가 실패한다.
  return (
    <Suspense fallback={null}>
      <DowntimeAnalysisRun />
    </Suspense>
  );
}

function DowntimeAnalysisRun() {
  const params = useSearchParams();
  const [sessionId] = useState(makeSessionId);
  const [dateFrom, setDateFrom] = useState(params.get("date_from") ?? today);
  const [dateTo, setDateTo] = useState(params.get("date_to") ?? today);
  const [lineId, setLineId] = useState(params.get("line_id") ?? "");
  const [equipmentId, setEquipmentId] = useState(params.get("equipment_id") ?? "");
  const [validationError, setValidationError] = useState("");
  const [equipment, setEquipment] = useState<EquipmentSummaryItem[]>([]);

  useEffect(() => {
    listEquipment().then(setEquipment).catch(() => {});
  }, []);
  const lines = useMemo(() => Array.from(new Set(equipment.map((e) => e.line_id))).sort(), [equipment]);
  const equipmentOptions = useMemo(
    () => equipment.filter((e) => !lineId || e.line_id === lineId).sort((a, b) => a.equipment_id.localeCompare(b.equipment_id)),
    [equipment, lineId],
  );

  function changeLine(next: string) {
    setLineId(next);
    if (next && equipmentId && !equipment.some((e) => e.equipment_id === equipmentId && e.line_id === next)) setEquipmentId("");
  }

  // 설비를 고르면 그 설비의 라인이 따라온다 (리포트는 라인·설비를 확정해서 저장한다).
  function changeEquipment(next: string) {
    setEquipmentId(next);
    const found = equipment.find((e) => e.equipment_id === next);
    if (found) setLineId(found.line_id);
  }

  // 주소로 설비만 넘어온 경우 설비 목록이 오면 라인을 채운다.
  useEffect(() => {
    if (equipmentId && !lineId) {
      const found = equipment.find((e) => e.equipment_id === equipmentId);
      if (found) setLineId(found.line_id);
    }
  }, [equipment, equipmentId, lineId]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<DowntimeReport | null>(null);

  // "새 분석 요청" 모달에서 넘어온 경우(autorun=1) 입력한 조건으로 한 번만 자동 실행한다.
  const autorunDone = useRef(false);
  useEffect(() => {
    if (params.get("autorun") !== "1" || autorunDone.current) return;
    autorunDone.current = true;
    void runAnalysis();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function runAnalysis(event?: FormEvent) {
    event?.preventDefault();
    if (dateFrom && dateTo && dateFrom > dateTo) {
      setValidationError("시작일은 종료일보다 늦을 수 없습니다.");
      return;
    }
    if (!lineId) {
      setValidationError("분석할 라인을 선택해 주세요.");
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
            <DateField value={dateFrom} onCommit={setDateFrom} label="조회 시작일" />
            <span>~</span>
            <DateField value={dateTo} onCommit={setDateTo} label="조회 종료일" />
          </div>
        </FilterCard>
        <FilterCard icon={<IconLine />} label="라인">
          <select value={lineId} onChange={(e) => changeLine(e.target.value)} aria-label="라인">
            <option value="" disabled>라인 선택</option>
            {lines.map((line) => (
              <option key={line} value={line}>{lineLabel(line)}</option>
            ))}
          </select>
        </FilterCard>
        <FilterCard icon={<IconEquipment />} label="설비">
          <select value={equipmentId} onChange={(e) => changeEquipment(e.target.value)} aria-label="설비">
            <option value="">선택한 라인의 전체 설비</option>
            {equipmentOptions.map((item) => (
              <option key={item.equipment_id} value={item.equipment_id}>{equipmentLabel(item)}</option>
            ))}
          </select>
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
