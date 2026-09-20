// backend GET /equipment 응답 (backend/db.py list_equipment_status). 설비 관리 화면용.
export type EquipmentStatus = "정상" | "주의" | "정지";

export interface EquipmentSummaryItem {
  equipment_id: string;
  line_id: string;
  equipment_type: string;
  status: EquipmentStatus;
  utilization_pct: number;
  last_checked: string | null;
  // 지금 "정지"인 설비가 언제 정지가 풀리는지(끝이 정해진 경우만, ISO+KST 오프셋).
  // 폴링(1분)을 기다리지 않고 이 시각에 딱 맞춰 다시 조회하는 데 쓴다 — lib/useLiveTick.ts.
  active_until: string | null;
  // 지금 정지 중인 원인(사람이 읽는 이름, 없으면 에러코드 그대로). 정지가 아니면 null.
  active_cause: string | null;
}
