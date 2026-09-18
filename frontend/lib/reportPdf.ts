import type { DowntimeCause, DowntimeReport } from "../types/report";

function escapeHtml(value: string): string {
  return value.replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[character] ?? character);
}

function causeMarkup(cause: DowntimeCause, index: number): string {
  const evidence = cause.evidence.trim() || "제공된 판단 근거가 없습니다.";
  return `<article class="cause">
    <h3>${index + 1}. ${escapeHtml(cause.error_code)}</h3>
    <dl>
      <dt>설명</dt><dd>${escapeHtml(cause.description)}</dd>
      <dt>심각도</dt><dd>${escapeHtml(cause.severity)}</dd>
      <dt>상태</dt><dd>${cause.is_confirmed ? "확정" : "확인 필요"}</dd>
      <dt>판단 근거</dt><dd>${escapeHtml(evidence)}</dd>
    </dl>
  </article>`;
}

function reportDocument(report: DowntimeReport): string {
  const causes = report.causes.length
    ? report.causes.map(causeMarkup).join("")
    : "<p class=\"empty\">분석된 원인이 없습니다.</p>";

  return `<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>MESTORY 분석 리포트</title>
  <style>
    @page { size: A4; margin: 18mm; }
    * { box-sizing: border-box; } body { color: #1f2937; font: 14px/1.6 "Malgun Gothic", "Apple SD Gothic Neo", Arial, sans-serif; }
    h1 { margin: 0; color: #342f6d; font-size: 24px; } h2 { margin: 28px 0 10px; font-size: 17px; } h3 { margin: 0 0 8px; font-size: 15px; }
    .subtitle { color: #64748b; margin: 3px 0 20px; } .conditions { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
    .conditions div, .panel, .cause { border: 1px solid #dbe3ea; border-radius: 8px; padding: 12px; } .conditions span, dt { color: #64748b; font-size: 12px; }
    .cause { break-inside: avoid; margin: 10px 0; } dl { margin: 0; } dt { margin-top: 8px; } dd { margin: 1px 0 0; overflow-wrap: anywhere; white-space: pre-wrap; }
    .panel { margin-top: 10px; } .data { background: #eefbfb; } .empty { color: #64748b; }
  </style></head><body>
    <h1>MESTORY 설비 다운타임 원인 분석 리포트</h1><p class="subtitle">분석 결과 저장본</p>
    <section class="conditions"><div><span>조회 기간</span><br>${escapeHtml(report.period)}</div><div><span>라인</span><br>${escapeHtml(report.line_id)}</div><div><span>설비</span><br>${escapeHtml(report.equipment_id)}</div></section>
    <h2>분석된 원인</h2>${causes}
    <section class="panel"><h2>권장 조치</h2><p>${escapeHtml(report.recommended_action)}</p></section>
    <section class="panel data"><h2>데이터 확인</h2><p>확인 필요한 데이터가 ${report.unclassified_count}건 있습니다.</p></section>
    <section class="panel"><h2>분석 참고 사항</h2><p>${escapeHtml(report.confidence_note)}</p></section>
  </body></html>`;
}

export function printReportAsPdf(report: DowntimeReport): boolean {
  if (typeof window === "undefined") return false;
  const printWindow = window.open("", "_blank", "width=900,height=700");
  if (!printWindow) return false;
  printWindow.document.open();
  printWindow.document.write(reportDocument(report));
  printWindow.document.close();
  printWindow.focus();
  printWindow.print();
  return true;
}
