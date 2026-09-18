import type { HistoryApiItem, HistorySaveInput } from "../types/authHistory";
import type { DowntimeReport, ReportRequest } from "../types/report";

function baseUrl() {
  const value = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (value) return value.replace(/\/+$/, "");
  if (process.env.NODE_ENV === "production") throw new Error("NEXT_PUBLIC_API_BASE_URL이 설정되지 않았습니다.");
  return "http://localhost:8000";
}

async function historyRequest<T>(path: string, token: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${baseUrl()}${path}`, { ...init, headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...init.headers } });
  if (!response.ok) throw new Error(`분석 기록 요청 실패 (HTTP ${response.status})`);
  return (await response.json()) as T;
}

export const saveAnalysisHistory = (token: string, payload: HistorySaveInput) => historyRequest<HistoryApiItem>("/history", token, { method: "POST", body: JSON.stringify(payload) });
export const listAnalysisHistory = (token: string) => historyRequest<HistoryApiItem[]>("/history", token);
export const getAnalysisHistory = (token: string, historyId: string) => historyRequest<HistoryApiItem>(`/history/${encodeURIComponent(historyId)}`, token);

/** 로그인 token이 있을 때만 호출하는 분석 성공 후 저장 helper다. */
export function saveReportHistory(token: string | null, request: ReportRequest, report: DowntimeReport): Promise<HistoryApiItem | null> {
  if (!token) return Promise.resolve(null);
  return saveAnalysisHistory(token, { date_from: request.date_from ?? null, date_to: request.date_to ?? null, line_id: request.line_id ?? null, equipment_id: request.equipment_id ?? null, report_json: report });
}
