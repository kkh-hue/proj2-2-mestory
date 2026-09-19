import type { ChatTurn, DowntimeReport, ReportRequest, ReportSummary, SavedReport } from "../types/report";
import type { DashboardSummary } from "../types/dashboard";
import type { AlertItem } from "../types/alert";
import type { EquipmentSummaryItem } from "../types/equipment";

export class ReportApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown,
  ) {
    super(`리포트 요청 실패 (HTTP ${status})`);
    this.name = "ReportApiError";
  }
}

function getBaseUrl(): string {
  let baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!baseUrl) {
    if (process.env.NODE_ENV === "production") {
      throw new Error("NEXT_PUBLIC_API_BASE_URL이 설정되지 않았습니다.");
    }
    baseUrl = "http://localhost:8000";
  }
  return baseUrl.replace(/\/+$/, "");
}

async function parseErrorBody(response: Response): Promise<unknown> {
  const text = await response.text();
  try {
    return JSON.parse(text);
  } catch {
    // 프록시/서버가 JSON 대신 텍스트를 반환해도 원문을 보존한다.
    return text;
  }
}

// session_id는 호출자가 관리한다. 리포트 생성 중복을 피하려고 재시도하지 않는다.
async function postReport(
  request: ReportRequest,
  options?: { signal?: AbortSignal },
): Promise<{ report: DowntimeReport; reportId: string | null }> {
  const response = await fetch(`${getBaseUrl()}/report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal: options?.signal,
  });

  if (!response.ok) {
    throw new ReportApiError(response.status, await parseErrorBody(response));
  }

  const report = (await response.json()) as DowntimeReport;
  return { report, reportId: response.headers.get("X-Report-Id") };
}

export async function createReport(
  request: ReportRequest,
  options?: { signal?: AbortSignal },
): Promise<DowntimeReport> {
  return (await postReport(request, options)).report;
}

// AI 원인분석 대화형 화면처럼 "방금 만든 리포트의 상세 페이지로 바로 이동"이 필요할 때 쓴다.
export async function createReportWithId(
  request: ReportRequest,
  options?: { signal?: AbortSignal },
): Promise<{ report: DowntimeReport; reportId: string | null }> {
  return postReport(request, options);
}

export async function getChatHistory(sessionId: string): Promise<ChatTurn[]> {
  const response = await fetch(`${getBaseUrl()}/chat/${encodeURIComponent(sessionId)}`);
  if (!response.ok) {
    throw new ReportApiError(response.status, await parseErrorBody(response));
  }
  return (await response.json()) as ChatTurn[];
}

export async function listReports(): Promise<ReportSummary[]> {
  const response = await fetch(`${getBaseUrl()}/reports`);
  if (!response.ok) {
    throw new ReportApiError(response.status, await parseErrorBody(response));
  }
  return (await response.json()) as ReportSummary[];
}

export async function getReport(reportId: string): Promise<SavedReport> {
  const response = await fetch(`${getBaseUrl()}/reports/${encodeURIComponent(reportId)}`);
  if (!response.ok) {
    throw new ReportApiError(response.status, await parseErrorBody(response));
  }
  return (await response.json()) as SavedReport;
}

// asOf: "YYYY-MM-DD". 상단 날짜 선택 — 안 주면 backend가 오늘 기준으로 계산한다.
export async function getDashboard(asOf?: string): Promise<DashboardSummary> {
  const query = asOf ? `?as_of=${encodeURIComponent(asOf)}` : "";
  const response = await fetch(`${getBaseUrl()}/dashboard${query}`);
  if (!response.ok) {
    throw new ReportApiError(response.status, await parseErrorBody(response));
  }
  return (await response.json()) as DashboardSummary;
}

export async function listAlerts(asOf?: string): Promise<AlertItem[]> {
  const query = asOf ? `?as_of=${encodeURIComponent(asOf)}` : "";
  const response = await fetch(`${getBaseUrl()}/alerts${query}`);
  if (!response.ok) {
    throw new ReportApiError(response.status, await parseErrorBody(response));
  }
  return (await response.json()) as AlertItem[];
}

export async function listEquipment(asOf?: string): Promise<EquipmentSummaryItem[]> {
  const query = asOf ? `?as_of=${encodeURIComponent(asOf)}` : "";
  const response = await fetch(`${getBaseUrl()}/equipment${query}`);
  if (!response.ok) {
    throw new ReportApiError(response.status, await parseErrorBody(response));
  }
  return (await response.json()) as EquipmentSummaryItem[];
}
