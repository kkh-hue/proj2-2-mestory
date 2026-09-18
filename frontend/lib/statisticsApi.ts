import type { ReportRequest } from "../types/report";
import type { ReportStatistics } from "../types/statistics";

export class StatisticsApiError extends Error {
  constructor(public readonly status: number, public readonly body: unknown) {
    super(`통계 요청 실패 (HTTP ${status})`);
    this.name = "StatisticsApiError";
  }
}

function getApiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (configured) return configured.replace(/\/+$/, "");
  if (process.env.NODE_ENV === "production") throw new Error("NEXT_PUBLIC_API_BASE_URL이 설정되지 않았습니다.");
  return "http://localhost:8000";
}

export async function fetchReportStatistics(request: ReportRequest, options?: { signal?: AbortSignal }): Promise<ReportStatistics> {
  const response = await fetch(`${getApiBaseUrl()}/report/statistics`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request), signal: options?.signal,
  });
  if (!response.ok) {
    const text = await response.text();
    let body: unknown = text;
    try { body = JSON.parse(text); } catch { /* text body is retained */ }
    throw new StatisticsApiError(response.status, body);
  }
  return (await response.json()) as ReportStatistics;
}
