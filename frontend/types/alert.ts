// backend GET /alerts 응답 (backend/db.py list_alerts). 알림센터 화면용.
// downtime_log·reports에서 파생된 값 — 전용 테이블이 없다.
export type AlertTone = "critical" | "warning" | "analysis";

export interface AlertItem {
  id: string;
  tone: AlertTone;
  tag: string;
  title: string;
  description: string;
  line_id: string | null;
  equipment_id: string | null; // 분석 완료 알림 중 라인 단위 분석은 null
  date: string;
  unread: boolean;
}
