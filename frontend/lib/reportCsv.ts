// 엑셀 다운로드는 의존성 추가 없이 CSV로 만든다 (엑셀이 CSV를 그대로 열 수 있고,
// xlsx 패키지는 npm 배포판에 고쳐지지 않은 취약점이 있어 쓰지 않는다).
import type { SavedReport } from "../types/report";

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

export function downloadCsv(report: SavedReport) {
  // BOM(﻿)을 앞에 붙여야 엑셀이 한글을 깨진 글자 없이 연다.
  const blob = new Blob([`﻿${toCsv(report)}`], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `mestory-report-${report.id}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}
