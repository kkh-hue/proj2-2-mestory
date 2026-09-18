// backend의 출력 계약(backend/services/llm.py)과 요청 스키마(backend/main.py)를 그대로 옮긴 타입.
// backend 쪽 필드가 바뀌면 여기도 같이 고쳐야 한다 — 둘이 어긋나면 프론트가 파싱에서 깨진다.

// "판정 불가": 사전에 없는 코드·빈 에러코드·데이터 오류(음수 등)·ETC-604처럼
// 근거가 없어 심각도를 정할 수 없는 경우. backend/services/llm.py의 DowntimeCause와 같아야 한다.
export type Severity = "경미" | "보통" | "중대" | "판정 불가";

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
  // 멀티모달 (docs/specs/multimodal.md). 이미지를 안 보낸 요청이면 null / false.
  visual_findings: string[] | null;
  used_image: boolean;
}

export interface ReportRequest {
  line_id?: string | null;
  equipment_id?: string | null;
  date_from?: string | null; // YYYY-MM-DD, 정지 시작일 기준
  date_to?: string | null; // YYYY-MM-DD, 정지 시작일 기준
  session_id?: string | null;
  // 에러 화면·설비 사진 data URL ("data:image/png;base64,...").
  // 최대 3장, 1장 5MB, 합계 10MB, png·jpeg·webp만 (backend/main.py에서 검증).
  images?: string[] | null;
}
