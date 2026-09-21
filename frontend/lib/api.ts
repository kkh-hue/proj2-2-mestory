import type { ChatSessionSummary, ChatTurn, DowntimeReport, ReportRequest, ReportSummary, SavedReport } from "../types/report";
import type { DashboardSummary } from "../types/dashboard";
import type { AlertItem } from "../types/alert";
import type { EquipmentSummaryItem } from "../types/equipment";
import type { DowntimeAnalysis, DowntimeAnalysisQuery } from "../types/downtimeAnalysis";

const READ_REQUEST_TIMEOUT_MS = 10_000;
// 메일 발송은 외부 서비스(Resend)를 거치므로 읽기보다 넉넉하게 준다.
// 서버 쪽 발송 제한이 15초라, 그보다 조금 길게 잡아야 "서버는 실패로 끝냈는데
// 화면만 먼저 포기하는" 어긋남이 생기지 않는다.
const EMAIL_REQUEST_TIMEOUT_MS = 20_000;
const ANALYSIS_REQUEST_TIMEOUT_MS = 120_000;

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

async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit | undefined,
  timeoutMs: number,
): Promise<Response> {
  const controller = new AbortController();
  const externalSignal = init?.signal;
  const abortFromCaller = () => controller.abort();
  externalSignal?.addEventListener("abort", abortFromCaller, { once: true });
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } catch (cause) {
    if (controller.signal.aborted && !externalSignal?.aborted) {
      throw new Error(`API 요청이 ${Math.round(timeoutMs / 1000)}초 안에 완료되지 않았습니다.`);
    }
    throw cause;
  } finally {
    clearTimeout(timeoutId);
    externalSignal?.removeEventListener("abort", abortFromCaller);
  }
}

// session_id는 호출자가 관리한다. 리포트 생성 중복을 피하려고 재시도하지 않는다.
async function postReport(
  request: ReportRequest,
  options?: { signal?: AbortSignal },
): Promise<{ report: DowntimeReport; reportId: string | null }> {
  const response = await fetchWithTimeout(`${getBaseUrl()}/report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal: options?.signal,
  }, ANALYSIS_REQUEST_TIMEOUT_MS);

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
  const response = await fetchWithTimeout(`${getBaseUrl()}/chat/${encodeURIComponent(sessionId)}`, undefined, READ_REQUEST_TIMEOUT_MS);
  if (!response.ok) {
    throw new ReportApiError(response.status, await parseErrorBody(response));
  }
  return (await response.json()) as ChatTurn[];
}

export async function listChatSessions(): Promise<ChatSessionSummary[]> {
  const response = await fetchWithTimeout(`${getBaseUrl()}/chat/sessions`, undefined, READ_REQUEST_TIMEOUT_MS);
  if (!response.ok) {
    throw new ReportApiError(response.status, await parseErrorBody(response));
  }
  return (await response.json()) as ChatSessionSummary[];
}

export async function listReports(): Promise<ReportSummary[]> {
  const response = await fetchWithTimeout(`${getBaseUrl()}/reports`, undefined, READ_REQUEST_TIMEOUT_MS);
  if (!response.ok) {
    throw new ReportApiError(response.status, await parseErrorBody(response));
  }
  return (await response.json()) as ReportSummary[];
}

export async function getReport(reportId: string): Promise<SavedReport> {
  const response = await fetchWithTimeout(`${getBaseUrl()}/reports/${encodeURIComponent(reportId)}`, undefined, READ_REQUEST_TIMEOUT_MS);
  if (!response.ok) {
    throw new ReportApiError(response.status, await parseErrorBody(response));
  }
  return (await response.json()) as SavedReport;
}

// 리포트를 메일로 보낸다 (docs/specs/report-email.md).
// 보내는 것은 받는 사람 주소 하나뿐이다 — 리포트 내용은 서버가 report_id로 직접 꺼낸다.
// 화면이 보낸 내용을 그대로 메일에 넣으면 요청을 조작해 아무 내용이나 보낼 수 있기 때문이다.
export async function sendReportEmail(reportId: string, to: string): Promise<void> {
  const response = await fetchWithTimeout(
    `${getBaseUrl()}/reports/${encodeURIComponent(reportId)}/email`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ to }) },
    // 읽기(10초)보다 넉넉하게 준다 — 메일 발송은 외부 서비스를 거치느라 더 걸린다.
    EMAIL_REQUEST_TIMEOUT_MS,
  );
  if (!response.ok) {
    throw new ReportApiError(response.status, await parseErrorBody(response));
  }
}

// asOf: "YYYY-MM-DD". 상단 날짜 선택 — 안 주면 backend가 오늘 기준으로 계산한다.
export async function getDashboard(asOf?: string): Promise<DashboardSummary> {
  const query = asOf ? `?as_of=${encodeURIComponent(asOf)}` : "";
  const response = await fetchWithTimeout(`${getBaseUrl()}/dashboard${query}`, undefined, READ_REQUEST_TIMEOUT_MS);
  if (!response.ok) {
    throw new ReportApiError(response.status, await parseErrorBody(response));
  }
  return (await response.json()) as DashboardSummary;
}

export async function listAlerts(asOf?: string): Promise<AlertItem[]> {
  const query = asOf ? `?as_of=${encodeURIComponent(asOf)}` : "";
  const response = await fetchWithTimeout(`${getBaseUrl()}/alerts${query}`, undefined, READ_REQUEST_TIMEOUT_MS);
  if (!response.ok) {
    throw new ReportApiError(response.status, await parseErrorBody(response));
  }
  return (await response.json()) as AlertItem[];
}

export async function listEquipment(asOf?: string): Promise<EquipmentSummaryItem[]> {
  const query = asOf ? `?as_of=${encodeURIComponent(asOf)}` : "";
  const response = await fetchWithTimeout(`${getBaseUrl()}/equipment${query}`, undefined, READ_REQUEST_TIMEOUT_MS);
  if (!response.ok) {
    throw new ReportApiError(response.status, await parseErrorBody(response));
  }
  return (await response.json()) as EquipmentSummaryItem[];
}

export async function getDowntimeAnalysis(query: DowntimeAnalysisQuery): Promise<DowntimeAnalysis> {
  const params = new URLSearchParams({ date_from: query.date_from, date_to: query.date_to, status: query.status });
  if (query.line_id) params.set("line_id", query.line_id);
  if (query.equipment_id) params.set("equipment_id", query.equipment_id);
  const response = await fetchWithTimeout(`${getBaseUrl()}/downtime/analysis?${params.toString()}`, undefined, READ_REQUEST_TIMEOUT_MS);
  if (!response.ok) {
    throw new ReportApiError(response.status, await parseErrorBody(response));
  }
  return (await response.json()) as DowntimeAnalysis;
}
