"use client";

import { useState } from "react";
import ChatInput from "../components/ChatInput";
import ChatWindow from "../components/ChatWindow";
import { createReport } from "../lib/api";
import type { DowntimeReport, ReportRequest } from "../types/report";

function makeSessionId() { return typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `session-${Date.now()}`; }

export default function Home() {
  const [sessionId] = useState(makeSessionId);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<DowntimeReport | null>(null);
  const [request, setRequest] = useState<Omit<ReportRequest, "session_id">>({
    date_from: null, date_to: null, line_id: null, equipment_id: null,
  });

  async function handleSubmit(request: Omit<ReportRequest, "session_id">) {
    setRequest(request);
    setLoading(true); setError(""); setResult(null);
    try { setResult(await createReport({ ...request, session_id: sessionId })); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "알 수 없는 오류가 발생했습니다."); }
    finally { setLoading(false); }
  }

  function startNewAnalysis() {
    setRequest({ date_from: null, date_to: null, line_id: null, equipment_id: null });
    setResult(null);
    setError("");
    setLoading(false);
  }

  return (
    <main className={`app-shell ${result ? "result-mode" : ""}`}>
      <header className="hero"><div className="brand-mark">M</div><div><div className="eyebrow">MANUFACTURING INTELLIGENCE</div><h1>MESTORY</h1><p>설비 다운타임 원인 분석 리포트</p></div></header>
      {loading || result || error ? <div className="screen-panel"><ChatWindow loading={loading} error={error} result={result} onNewAnalysis={startNewAnalysis} onRetry={() => handleSubmit(request)} /></div> : <div className="input-screen"><ChatInput loading={loading} initialRequest={request} onSubmit={handleSubmit} /></div>}
    </main>
  );
}
