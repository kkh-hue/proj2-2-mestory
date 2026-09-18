// backend GET /equipment 응답 (backend/db.py list_equipment_status). 설비 관리 화면용.
export type EquipmentStatus = "정상" | "주의" | "정지";

export interface EquipmentSummaryItem {
  equipment_id: string;
  line_id: string;
  equipment_type: string;
  status: EquipmentStatus;
  utilization_pct: number;
  last_checked: string | null;
}
