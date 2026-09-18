"use client";

import { FormEvent, useState } from "react";
import type { ReportRequest } from "../types/report";

type Props = {
  loading: boolean;
  initialRequest: Omit<ReportRequest, "session_id">;
  onSubmit: (request: Omit<ReportRequest, "session_id">) => void;
};

export default function ChatInput({ loading, initialRequest, onSubmit }: Props) {
  const [dateFrom, setDateFrom] = useState(initialRequest.date_from ?? "");
  const [dateTo, setDateTo] = useState(initialRequest.date_to ?? "");
  const [lineId, setLineId] = useState(initialRequest.line_id ?? "");
  const [equipmentId, setEquipmentId] = useState(initialRequest.equipment_id ?? "");
  const [validationError, setValidationError] = useState("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (dateFrom && dateTo && dateFrom > dateTo) {
      setValidationError("시작일은 종료일보다 늦을 수 없습니다.");
      return;
    }
    setValidationError("");
    onSubmit({
      date_from: dateFrom || null,
      date_to: dateTo || null,
      line_id: lineId.trim() || null,
      equipment_id: equipmentId.trim() || null,
    });
  }

  return (
    <form className="query-card" onSubmit={submit}>
      <div className="section-kicker">ANALYSIS REQUEST</div>
      <h2>다운타임 원인 분석</h2>
      <p className="muted">분석할 기간과 설비 조건을 입력해 주세요.</p>
      <p className="helper-text">라인 ID와 설비 ID를 입력하지 않으면 전체 데이터를 대상으로 분석합니다.</p>
      <fieldset className="date-range">
        <legend>조회 기간</legend>
        <div className="date-range-fields">
          <label>시작일<input aria-label="조회 시작일" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} /></label>
          <span className="date-separator" aria-hidden="true">~</span>
          <label>종료일<input aria-label="조회 종료일" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} /></label>
        </div>
      </fieldset>
      <div className="field-grid">
        <label>라인 ID<input placeholder="예: LINE-A" value={lineId} onChange={(e) => setLineId(e.target.value)} /></label>
        <label>설비 ID<input placeholder="예: EQ-001" value={equipmentId} onChange={(e) => setEquipmentId(e.target.value)} /></label>
      </div>
      {validationError && <p className="form-error" role="alert">{validationError}</p>}
      <button className="primary-button" type="submit" disabled={loading}>
        {loading ? "분석 중..." : "분석 시작"}
      </button>
    </form>
  );
}
