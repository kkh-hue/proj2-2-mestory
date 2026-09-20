"use client";

import { useEffect } from "react";
import type { AnalysisCause } from "../types/downtimeAnalysis";
import { IconX } from "./icons";

function formatMinutes(min: number) {
  const total = Math.round(min);
  const h = Math.floor(total / 60);
  const m = total % 60;
  return h > 0 ? `${h}h ${String(m).padStart(2, "0")}m` : `${m}m`;
}

function formatOccurred(iso: string | null) {
  return iso ? `${iso.slice(0, 10).replaceAll("-", ".")} ${iso.slice(11, 16)}` : "-";
}

// 다운타임 원인 상세 표의 행을 눌렀을 때 뜨는 설명 화면.
// 설명(일반적 원인·보통 정지시간·기본 심각도)은 error_code_dict 값이고,
// 건수·시간·비중은 지금 선택한 조회 조건의 집계 값이다.
export default function CauseInfoModal({ cause, onClose }: { cause: AnalysisCause; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const registered = cause.typical_cause !== null || cause.severity_hint !== null;
  const average = cause.count > 0 ? cause.downtime_min / cause.count : 0;

  const stats = [
    { label: "발생 건수", value: `${cause.count}건` },
    { label: "총 다운타임", value: formatMinutes(cause.downtime_min) },
    { label: "건당 평균", value: formatMinutes(average) },
    { label: "전체 비중", value: `${cause.percent}%` },
  ];

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="cause-info-title" onClick={onClose}>
      <div className="modal-panel cause-info-panel" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="modal-close" onClick={onClose} aria-label="닫기">
          <IconX />
        </button>
        <span className="section-kicker">{cause.category} · {cause.error_code}</span>
        <h2 id="cause-info-title" className="modal-title">{cause.label}</h2>
        <p className="modal-subtitle">선택한 조회 조건에서 이 원인이 차지한 다운타임입니다.</p>

        <div className="cause-info-stats">
          {stats.map((s) => (
            <div key={s.label}>
              <span className="insight-label">{s.label}</span>
              <div className="insight-value">{s.value}</div>
            </div>
          ))}
        </div>

        <dl className="cause-info-list">
          <div>
            <dt>최근 발생</dt>
            <dd>{formatOccurred(cause.last_occurred)}</dd>
          </div>
          {registered ? (
            <>
              <div>
                <dt>일반적인 원인</dt>
                <dd>{cause.typical_cause ?? "-"}</dd>
              </div>
              <div>
                <dt>보통 정지 시간</dt>
                <dd>{cause.typical_duration_range ? `${cause.typical_duration_range}분` : "-"}</dd>
              </div>
              <div>
                <dt>기본 심각도</dt>
                <dd>{cause.severity_hint ?? "-"}</dd>
              </div>
            </>
          ) : (
            <div>
              <dt>설명</dt>
              <dd>에러코드 사전에 없는 코드라 원인 설명이 없습니다. 현장 확인이 필요합니다.</dd>
            </div>
          )}
        </dl>
      </div>
    </div>
  );
}
