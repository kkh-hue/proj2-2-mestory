// 콤보박스·목록에서 코드(LINE-A, EQ-001) 대신 사람이 읽는 이름을 보여주기 위한 표기 규칙.
// DB에는 라인/설비 이름 컬럼이 없어서 라인은 코드에서 "A라인"을 만들고,
// 설비는 equipment_type(사출성형기 등)을 이름으로 쓴다.
// 같은 라인에 같은 종류 설비가 여러 대라 이름만으로는 구분이 안 되므로 설비 ID를 뒤에 덧붙인다.

export function lineLabel(lineId: string | null | undefined): string {
  if (!lineId) return "-";
  const match = /^LINE-(.+)$/i.exec(lineId);
  return match ? `${match[1]}라인` : lineId;
}

export function equipmentLabel(item: { equipment_id: string; equipment_type?: string | null }): string {
  return item.equipment_type ? `${item.equipment_type} · ${item.equipment_id}` : item.equipment_id;
}

// 리포트 제목/부제용 범위 표기. 리포트에 저장된 line_id·equipment_id는 조회 조건 그대로라
// 조건을 안 준 리포트는 "전체 라인"/"전체 설비"가 들어 있다 — 그런 값은 특정 설비가 아니다.
export function reportScope(
  report: { line_id: string; equipment_id: string },
  equipment: { equipment_id: string; line_id: string; equipment_type: string }[],
): string {
  const item = equipment.find((e) => e.equipment_id === report.equipment_id);
  if (item) return `${lineLabel(item.line_id)} · ${equipmentLabel(item)}`;
  if (report.equipment_id.startsWith("EQ-")) return `${lineLabel(report.line_id)} · ${report.equipment_id}`;
  if (report.line_id.startsWith("LINE-")) return `${lineLabel(report.line_id)} 전체 설비`;
  return "전체 설비 종합";
}

export function reportTitle(
  report: { line_id: string; equipment_id: string },
  equipment: { equipment_id: string; line_id: string; equipment_type: string }[],
): string {
  return `${reportScope(report, equipment)} 원인 분석 리포트`;
}
