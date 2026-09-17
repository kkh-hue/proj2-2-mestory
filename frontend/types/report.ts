// backend의 출력 계약(backend/services/llm.py)과 요청 스키마(backend/main.py)를 그대로 옮긴 타입.
// backend 쪽 필드가 바뀌면 여기도 같이 고쳐야 한다 — 둘이 어긋나면 프론트가 파싱에서 깨진다.

export type Severity = "경미" | "보통" | "중대";

export interface DowntimeCause {
  error_code: string;
  description: string;
  severity: Severity;
  evidence: string;
  is_confirmed: boolean;
}

export interface DowntimeReport {
  equipment_id: string;
  line_id: string;
  period: string;
  causes: DowntimeCause[];
  unclassified_count: number;
  confidence_note: string;
  recommended_action: string;
}

export interface ReportRequest {
  line_id?: string | null;
  equipment_id?: string | null;
  date_from?: string | null; // YYYY-MM-DD, 정지 시작일 기준
  date_to?: string | null; // YYYY-MM-DD, 정지 시작일 기준
  session_id?: string | null;
}
