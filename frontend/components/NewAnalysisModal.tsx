"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { IconCalendar, IconEquipment, IconFolder, IconPlus, IconTarget, IconX } from "./icons";

const SCOPES = ["전체 원인", "전기", "기계", "공정"] as const;

export default function NewAnalysisModal() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [scope, setScope] = useState<(typeof SCOPES)[number]>("전체 원인");
  const [memo, setMemo] = useState("");

  function goToRealAnalysis() {
    setOpen(false);
    router.push("/downtime/report");
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
                      <input type="date" defaultValue="2026-09-12" />
                    </label>
                    <label>
                      종료일
                      <input type="date" defaultValue="2026-09-18" />
                    </label>
                  </div>
                </div>

                <div className="modal-field">
                  <span className="modal-field-label">
                    <IconFolder /> 라인 선택
                  </span>
                  <select defaultValue="">
                    <option value="">전체 라인</option>
                    <option value="LINE-A">LINE-A</option>
                    <option value="LINE-B">LINE-B</option>
                    <option value="LINE-C">LINE-C</option>
                  </select>
                </div>

                <div className="modal-field">
                  <span className="modal-field-label">
                    <IconEquipment /> 설비 선택
                  </span>
                  <select defaultValue="">
                    <option value="">전체 설비</option>
                    <option value="EQ-021">EQ-021</option>
                    <option value="EQ-114">EQ-114</option>
                  </select>
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
                  <span className="modal-info-label">예상 분석 데이터</span>
                  <div className="modal-info-value">1,248건</div>
                </div>
                <hr />
                <div>
                  <span className="modal-info-label">예상 소요 시간</span>
                  <div className="modal-info-value">약 2분</div>
                </div>
                <p className="modal-info-note">선택한 조건에 따라 예상되는 분석 데이터 수와 소요 시간을 안내합니다.</p>
              </aside>
            </div>

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
