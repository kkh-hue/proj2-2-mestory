// "설비 관리" 화면 목업 데이터 — 다른 화면과 같은 이유로 정적 값을 씀.
// 실제 설비 마스터/상태 조회 엔드포인트가 생기면 교체 대상.

export type EquipmentStatus = "정상" | "주의" | "정지";

export const equipmentSummary = [
  { key: "total", label: "전체 설비", value: "48대", note: "등록된 전체 설비 수" },
  { key: "ok", label: "정상 가동", value: "42대", note: "정상적으로 가동 중인 설비" },
  { key: "warn", label: "점검 필요", value: "4대", note: "점검이 필요한 설비" },
  { key: "stop", label: "정지", value: "2대", note: "현재 정지 상태인 설비" },
] as const;

export type EquipmentItem = {
  id: string;
  icon: "stamp" | "robotArm" | "eye" | "conveyor" | "pump" | "fan" | "panel";
  name: string;
  line: string;
  status: EquipmentStatus;
  utilization: number;
  lastChecked: string;
};

export const equipmentList: EquipmentItem[] = [
  { id: "EQ-021", icon: "stamp", name: "프레스 라인", line: "LINE-A", status: "정상", utilization: 98.7, lastChecked: "2026.09.16" },
  { id: "EQ-114", icon: "robotArm", name: "조립 로봇", line: "LINE-B", status: "정상", utilization: 94.2, lastChecked: "2026.09.15" },
  { id: "EQ-008", icon: "eye", name: "비전 검사기", line: "LINE-C", status: "주의", utilization: 86.5, lastChecked: "2026.09.14" },
  { id: "EQ-032", icon: "conveyor", name: "컨베이어 모터", line: "LINE-A", status: "정지", utilization: 0.0, lastChecked: "2026.09.10" },
  { id: "EQ-046", icon: "pump", name: "펌프 모터", line: "LINE-B", status: "정상", utilization: 97.3, lastChecked: "2026.09.17" },
  { id: "EQ-067", icon: "robotArm", name: "포장 로봇", line: "LINE-C", status: "주의", utilization: 81.9, lastChecked: "2026.09.13" },
  { id: "EQ-095", icon: "fan", name: "공기 압축기", line: "LINE-A", status: "정상", utilization: 96.4, lastChecked: "2026.09.16" },
  { id: "EQ-118", icon: "panel", name: "제어 판넬", line: "LINE-B", status: "정상", utilization: 92.1, lastChecked: "2026.09.15" },
];
