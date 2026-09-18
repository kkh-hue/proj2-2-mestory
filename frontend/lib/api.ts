import type { DowntimeReport, ReportRequest } from "../types/report";

export class ReportApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown,
  ) {
    super(`리포트 요청 실패 (HTTP ${status})`);
    this.name = "ReportApiError";
  }
}

// session_id는 호출자가 관리한다. 리포트 생성 중복을 피하려고 재시도하지 않는다.
export async function createReport(
  request: ReportRequest,
  options?: { signal?: AbortSignal },
): Promise<DowntimeReport> {
  let baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!baseUrl) {
    if (process.env.NODE_ENV === "production") {
      throw new Error("NEXT_PUBLIC_API_BASE_URL이 설정되지 않았습니다.");
    }
    baseUrl = "http://localhost:8000";
  }

  const response = await fetch(`${baseUrl.replace(/\/+$/, "")}/report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal: options?.signal,
  });

  if (!response.ok) {
    const text = await response.text();
    let body: unknown = text;
    try {
      body = JSON.parse(text);
    } catch {
      // 프록시/서버가 JSON 대신 텍스트를 반환해도 원문을 보존한다.
    }
    throw new ReportApiError(response.status, body);
  }

  return (await response.json()) as DowntimeReport;
}
