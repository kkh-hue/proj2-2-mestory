import type { DowntimeReport } from "./report";

/** `session_id`와 무관한 향후 인증 주체 식별자다. */
export type AuthenticatedUser = { user_id: string; display_name?: string | null };

export type LoginCredentials = { email: string; password: string };

/** 실제 인증 방식이 결정되기 전의 프론트 연결 계약이다. */
export type LoginHandler = (credentials: LoginCredentials) => Promise<AuthenticatedUser>;

export type AnalysisHistoryEntry = {
  analysis_id: string;
  user_id: string;
  created_at: string;
  period: string;
  line_id: string;
  equipment_id: string;
  report: DowntimeReport;
};

export type AnalysisHistoryRepository = {
  listForUser: (userId: string) => Promise<AnalysisHistoryEntry[]>;
  getById: (userId: string, analysisId: string) => Promise<AnalysisHistoryEntry | null>;
};

export type AuthSession = { access_token: string; token_type: "bearer"; expires_in: number; user: AuthenticatedUser };

export type HistorySaveInput = {
  date_from: string | null;
  date_to: string | null;
  line_id: string | null;
  equipment_id: string | null;
  report_json: DowntimeReport;
};

export type HistoryApiItem = HistorySaveInput & { history_id: string; analyzed_at: string };
