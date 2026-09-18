// 다운타임 분석 — 조건 입력 후 실제 backend POST /report를 호출하는 화면 (PRD F-07 원안, 대시보드에서 옮겨옴)
"use client";

import { useState } from "react";
import ChatInput from "../../components/ChatInput";
import ChatWindow from "../../components/ChatWindow";
import { createReport } from "../../lib/api";
import type { DowntimeReport, ReportRequest } from "../../types/report";

function makeSessionId() {
  return typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `session-${Date.now()}`;
}

export default function DowntimeAnalysisPage() {
  const [sessionId] = useState(makeSessionId);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<DowntimeReport | null>(null);
  const [request, setRequest] = useState<Omit<ReportRequest, "session_id">>({
    date_from: null,
    date_to: null,
    line_id: null,
    equipment_id: null,
  });

  async function handleSubmit(nextRequest: Omit<ReportRequest, "session_id">) {
    setRequest(nextRequest);
    setLoading(true);
    setError("");
    setResult(null);
    try {
      setResult(await createReport({ ...nextRequest, session_id: sessionId }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "알 수 없는 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  }

  function startNewAnalysis() {
    setRequest({ date_from: null, date_to: null, line_id: null, equipment_id: null });
    setResult(null);
    setError("");
    setLoading(false);
  }

  return (
    <main className={`app-shell ${result ? "result-mode" : ""}`}>
      <header className="hero">
        <div className="brand-mark">M</div>
        <div>
          <div className="eyebrow">MANUFACTURING INTELLIGENCE</div>
          <h1>다운타임 분석</h1>
          <p>조건을 입력하면 실제 원인 분석 리포트를 생성합니다.</p>
        </div>
      </header>
      {loading || result || error ? (
        <div className="screen-panel">
          <ChatWindow loading={loading} error={error} result={result} onNewAnalysis={startNewAnalysis} onRetry={() => handleSubmit(request)} />
        </div>
      ) : (
        <div className="input-screen">
          <ChatInput loading={loading} initialRequest={request} onSubmit={handleSubmit} />
        </div>
      )}
    </main>
  );
}
