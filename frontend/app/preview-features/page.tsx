"use client";

import CauseList from "../../components/CauseList";
import KpiSummary from "../../components/KpiSummary";
import PdfDownloadButton from "../../components/PdfDownloadButton";
import TopDowntimeChart from "../../components/TopDowntimeChart";
import type { DowntimeReport } from "../../types/report";

// UI 미리보기용 샘플 데이터입니다. 실제 Backend/API/DB 분석 결과가 아닙니다.
const previewReport: DowntimeReport = {
  period: "2026-09-01 ~ 2026-09-07", line_id: "LINE-A", equipment_id: "EQ-101",
  causes: [
    { error_code: "E-104", description: "센서 신호 이상", severity: "중대", is_confirmed: true, evidence: "PREVIEW: 오류 로그와 정지 구간이 일치합니다." },
    { error_code: "E-205", description: "공급 압력 변동", severity: "보통", is_confirmed: false, evidence: "PREVIEW: 현장 압력계 추가 확인이 필요합니다." },
    { error_code: "E-310", description: "안전 인터록 지연", severity: "경미", is_confirmed: true, evidence: "PREVIEW: 짧은 정지 기록이 반복됩니다." },
  ],
  recommended_action: "PREVIEW 권장 조치: 센서 배선과 압력 공급 장치를 우선 점검하세요.",
  confidence_note: "PREVIEW 분석 참고 사항입니다. 실제 분석 결과가 아닙니다.", unclassified_count: 2,
};
const topItems = [{ error_code: "E-104", total_downtime_min: 78, count: 4 }, { error_code: "E-205", total_downtime_min: 42, count: 3 }, { error_code: "E-310", total_downtime_min: 22, count: 2 }];

export default function FeaturePreviewPage() {
  return <main className="app-shell result-mode preview-page">
    <header className="hero preview-header"><div className="preview-brand"><div className="brand-mark">M</div><div><div className="eyebrow">RESULT SCREEN PREVIEW</div><h1>MESTORY</h1><p>설비 다운타임 원인 분석 리포트</p></div></div><button className="preview-login" type="button" onClick={() => undefined}>로그인</button></header>
    <article className="report-card preview-report">
      <p className="preview-notice">UI 미리보기용 샘플 데이터 · 실제 Backend, API, DB, 인증과 연결되지 않습니다.</p>
      <div className="report-heading"><div><div className="section-kicker">ANALYSIS RESULT</div><h2>다운타임 원인 분석 리포트</h2></div><span className="report-period">{previewReport.period}</span></div>
      <section className="preview-section"><h3>분석 조건</h3><div className="condition-row"><span>조회 기간 <b>{previewReport.period}</b></span><span>라인 <b>{previewReport.line_id}</b></span><span>설비 <b>{previewReport.equipment_id}</b></span></div></section>
      <section className="preview-section"><h3>KPI 요약</h3><KpiSummary data={{ total_downtime_min: 186, record_count: 12, unplanned_downtime_min: 142 }} /></section>
      <section className="preview-section preview-chart"><TopDowntimeChart items={topItems} codeSummaryDowntimeMin={142} /></section>
      <section className="cause-section preview-section"><div className="cause-title"><h3>분석된 원인</h3><span>{previewReport.causes.length}건</span></div><CauseList causes={previewReport.causes} /></section>
      <section className="recommendation-panel"><h3>권장 조치</h3><p>{previewReport.recommended_action}</p></section>
      <section className="data-panel"><h3>데이터 확인</h3><p>확인 필요한 데이터가 {previewReport.unclassified_count}건 있습니다.</p></section>
      <section className="note-panel"><h3>분석 참고 사항</h3><p>{previewReport.confidence_note}</p></section>
      <section className="preview-section preview-pdf"><h3>PDF로 저장</h3><p>미리보기 샘플 내용을 브라우저 인쇄 창에서 PDF로 저장합니다.</p><PdfDownloadButton report={previewReport} /></section>
      <div className="new-analysis-action"><button className="secondary-button" type="button" onClick={() => undefined}>← 새 분석하기</button></div>
    </article>
    <style jsx>{`
      .preview-header{align-items:center;justify-content:space-between;gap:24px}.preview-brand{display:flex;align-items:center;gap:14px}.preview-login{border:1px solid #c9c5e8;border-radius:8px;background:#fff;color:#4338a8;padding:9px 14px;font-weight:700;white-space:nowrap}.preview-report{max-width:980px;margin:0 auto}.preview-notice{margin:0 0 20px;padding:10px 12px;border-radius:8px;background:#eff6ff;color:#31537a;font-size:13px}.preview-section{margin-top:24px}.preview-section>h3{margin:0 0 10px}.preview-pdf{padding:16px;border:1px solid #ddd6fe;border-radius:10px;background:#f7f5ff}
      :global(.preview-page .kpi-summary){display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}:global(.preview-page .kpi-summary>div){padding:18px;border:1px solid #dce6eb;border-radius:10px;background:#fff}:global(.preview-page .kpi-summary span){display:block;color:#64748b;font-size:13px}:global(.preview-page .kpi-summary strong){display:block;margin-top:5px;color:#2c2768;font-size:24px}
      :global(.preview-chart .top-downtime-chart){padding:18px;border:1px solid #dce6eb;border-radius:10px;background:#fff}:global(.preview-chart .top-downtime-chart h3){margin-top:0}:global(.preview-chart .top-downtime-chart ol){display:grid;gap:13px;margin:0;padding:0;list-style:none}:global(.preview-chart .top-downtime-chart li){display:grid;grid-template-columns:74px 1fr auto;align-items:center;gap:12px}:global(.preview-chart .top-downtime-chart li::before){content:"";grid-column:2;grid-row:1;height:12px;border-radius:999px;background:#8076c8}:global(.preview-chart .top-downtime-chart li:nth-child(1)::before){width:100%}:global(.preview-chart .top-downtime-chart li:nth-child(2)::before){width:54%}:global(.preview-chart .top-downtime-chart li:nth-child(3)::before){width:28%}:global(.preview-chart .top-downtime-chart b){grid-column:1;grid-row:1}:global(.preview-chart .top-downtime-chart span){grid-column:3;grid-row:1;color:#475569;font-size:13px;white-space:nowrap}
      @media(max-width:640px){.preview-header,.preview-brand{align-items:flex-start}.preview-header{flex-direction:column}:global(.preview-page .kpi-summary){grid-template-columns:1fr}:global(.preview-chart .top-downtime-chart li){grid-template-columns:62px 1fr}:global(.preview-chart .top-downtime-chart span){grid-column:2;grid-row:2}}
    `}</style>
  </main>;
}
