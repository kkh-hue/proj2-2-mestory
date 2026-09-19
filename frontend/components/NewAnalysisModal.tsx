"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { listEquipment } from "../lib/api";
import { todayKst } from "../lib/date";
import type { EquipmentSummaryItem } from "../types/equipment";
import { IconCalendar, IconEquipment, IconFolder, IconPlus, IconTarget, IconX } from "./icons";

const SCOPES = ["전체 원인", "전기", "기계", "공정"] as const;

export default function NewAnalysisModal() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [scope, setScope] = useState<(typeof SCOPES)[number]>("전체 원인");
  const [memo, setMemo] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [lineId, setLineId] = useState("");
  const [equipmentId, setEquipmentId] = useState("");
  const [equipment, setEquipment] = useState<EquipmentSummaryItem[]>([]);
  const [optionsError, setOptionsError] = useState(false);
  const [validationError, setValidationError] = useState("");

  // 열 때마다 오늘(KST)로 초기화하고, 라인·설비 목록은 실제 /equipment 데이터에서 가져온다.
  useEffect(() => {
    if (!open) return;
    const today = todayKst();
    setDateFrom(today);
    setDateTo(today);
    setLineId("");
    setEquipmentId("");
    setValidationError("");
    setOptionsError(false);
    let cancelled = false;
    listEquipment()
      .then((items) => !cancelled && setEquipment(items))
      .catch(() => !cancelled && setOptionsError(true));
    return () => {
      cancelled = true;
    };
  }, [open]);

  const lines = useMemo(() => [...new Set(equipment.map((e) => e.line_id))].sort(), [equipment]);
  const equipmentOptions = useMemo(
    () => equipment.filter((e) => !lineId || e.line_id === lineId).map((e) => e.equipment_id).sort(),
    [equipment, lineId],
  );

  function goToRealAnalysis() {
    if (dateFrom && dateTo && dateFrom > dateTo) {
      setValidationError("시작일은 종료일보다 늦을 수 없습니다.");
      return;
    }
    const params = new URLSearchParams({ autorun: "1" });
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    if (lineId) params.set("line_id", lineId);
    if (equipmentId) params.set("equipment_id", equipmentId);
    setOpen(false);
    router.push(`/downtime/report?${params.toString()}`);
  }

  return (
    <>
      <button type="button" className="new-analysis-button" onClick={() => setOpen(true)}>
        <IconPlus />
        새 분석 요청
      </button>

      {open && (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="new-analysis-title">
          <div className="modal-panel">
            <button type="button" className="modal-close" onClick={() => setOpen(false)} aria-label="닫기">
              <IconX />
            </button>
            <span className="section-kicker">ANALYSIS REQUEST</span>
            <h2 id="new-analysis-title" className="modal-title">
              새 다운타임 분석 요청
            </h2>
            <p className="modal-subtitle">분석할 기간과 설비 조건을 입력하세요.</p>

            <div className="modal-body">
              <div className="modal-form">
                <div className="modal-field">
                  <span className="modal-field-label">
                    <IconCalendar /> 조회 기간
                  </span>
                  <div className="modal-date-fields">
                    <label>
                      시작일
                      <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
                    </label>
                    <label>
                      종료일
                      <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
                    </label>
                  </div>
                </div>

                <div className="modal-field">
                  <span className="modal-field-label">
                    <IconFolder /> 라인 선택
                  </span>
                  <select
                    value={lineId}
                    onChange={(e) => {
                      setLineId(e.target.value);
                      setEquipmentId("");
                    }}
                  >
                    <option value="">전체 라인</option>
                    {lines.map((id) => (
                      <option key={id} value={id}>
                        {id}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="modal-field">
                  <span className="modal-field-label">
                    <IconEquipment /> 설비 선택
                  </span>
                  <select value={equipmentId} onChange={(e) => setEquipmentId(e.target.value)}>
                    <option value="">전체 설비</option>
                    {equipmentOptions.map((id) => (
                      <option key={id} value={id}>
                        {id}
                      </option>
                    ))}
                  </select>
                  {optionsError && <span className="form-error">라인·설비 목록을 불러오지 못했습니다.</span>}
                </div>

                <div className="modal-field">
                  <span className="modal-field-label">
                    <IconTarget /> 분석 범위
                  </span>
                  <div className="scope-options">
                    {SCOPES.map((option) => (
                      <button
                        type="button"
                        key={option}
                        className={`scope-option${scope === option ? " active" : ""}`}
                        onClick={() => setScope(option)}
                      >
                        <span className="scope-radio" />
                        {option}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="modal-field">
                  <span className="modal-field-label">
                    <IconTarget /> 메모 (선택)
                  </span>
                  <textarea
                    placeholder="메모를 입력하세요."
                    maxLength={500}
                    value={memo}
                    onChange={(e) => setMemo(e.target.value)}
                  />
                  <span className="modal-char-count">{memo.length}/500</span>
                </div>
              </div>

              <aside className="modal-info-panel">
                <div>
                  <span className="modal-info-label">분석 조건 요약</span>
                  <div className="modal-info-value">{dateFrom === dateTo ? dateFrom : `${dateFrom} ~ ${dateTo}`}</div>
                </div>
                <p className="modal-info-note">
                  {lineId || "전체 라인"} · {equipmentId || "전체 설비"}
                  <br />
                  "분석 시작"을 누르면 이 조건으로 분석을 실행합니다.
                </p>
              </aside>
            </div>

            {validationError && <p className="form-error" role="alert">{validationError}</p>}
            <div className="modal-footer">
              <button type="button" className="secondary-button" onClick={() => setOpen(false)}>
                취소
              </button>
              <button type="button" className="primary-button-inline" onClick={goToRealAnalysis}>
                분석 시작
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
