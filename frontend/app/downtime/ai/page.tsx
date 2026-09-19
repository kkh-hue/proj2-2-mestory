// AI 원인 분석 — 대화형 화면 (F-07). backend POST /report(session_id·message)를 그대로 호출한다.
// session_id는 브라우저 localStorage에 저장해 재방문해도 같은 대화가 이어지고,
// 대화 자체는 backend/db.py(Postgres)에 저장돼 재배포해도 남는다.
// 원인별 분석/인사이트는 CauseBreakdown·InsightPanel을 그대로 재사용한다 —
// 출력 계약에 없는 수치(발생 시점·영향 시간 등)는 이 화면에서도 지어내지 않는다.
"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import CauseBreakdown from "../../../components/CauseBreakdown";
import InsightPanel from "../../../components/InsightPanel";
import Topbar from "../../../components/Topbar";
import { IconReport, IconRobot, IconSend, IconStopCircle, IconTriangleWarning, IconUser } from "../../../components/icons";
import { createReportWithId, getChatHistory, listEquipment } from "../../../lib/api";
import type { ChatTurn, SavedReport } from "../../../types/report";
import type { EquipmentSummaryItem } from "../../../types/equipment";

const SESSION_STORAGE_KEY = "mestory:ai-chat-session-id";

function loadOrCreateSessionId(): string {
  if (typeof window === "undefined") return "";
  const existing = window.localStorage.getItem(SESSION_STORAGE_KEY);
  if (existing) return existing;
  const created = crypto.randomUUID();
  window.localStorage.setItem(SESSION_STORAGE_KEY, created);
  return created;
}

function formatTime(iso: string) {
  const date = new Date(iso);
  return `${date.getMonth() + 1}.${date.getDate()} ${date.getHours().toString().padStart(2, "0")}:${date
    .getMinutes()
    .toString()
    .padStart(2, "0")}`;
}

export default function AiAnalysisChatPage() {
  const [sessionId, setSessionId] = useState("");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [hydrating, setHydrating] = useState(true);
  const [reviewNeeded, setReviewNeeded] = useState<EquipmentSummaryItem[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const id = loadOrCreateSessionId();
    setSessionId(id);
    if (!id) return;
    getChatHistory(id)
      .then(setTurns)
      .catch(() => setTurns([]))
      .finally(() => setHydrating(false));
  }, []);

  // 사용자가 57대 설비 상태를 일일이 파악할 수 없으니, 확인이 필요한(정상이 아닌)
  // 설비만 추려 버튼으로 먼저 보여준다 — 설비관리 화면과 같은 status 값을 그대로 쓴다.
  useEffect(() => {
    listEquipment()
      .then((items) => setReviewNeeded(items.filter((item) => item.status !== "정상")))
      .catch(() => setReviewNeeded([]));
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, loading]);

  const lastReport: SavedReport | undefined = [...turns].reverse().find((t) => t.report)?.report;

  async function submitQuestion(rawQuestion: string) {
    const question = rawQuestion.trim();
    if (!question || loading || !sessionId) return;

    setInput("");
    setError("");
    const askedAt = new Date().toISOString();
    setTurns((prev) => [...prev, { role: "user", content: question, created_at: askedAt }]);
    setLoading(true);

    try {
      const { report, reportId } = await createReportWithId({ session_id: sessionId, message: question });
      const savedReport: SavedReport | undefined = reportId
        ? { ...report, id: reportId, session_id: sessionId, created_at: new Date().toISOString() }
        : undefined;
      setTurns((prev) => [
        ...prev,
        { role: "assistant", content: report.recommended_action, created_at: new Date().toISOString(), report: savedReport },
      ]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "알 수 없는 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    void submitQuestion(input);
  }

  return (
    <main className="page">
      <Topbar title="AI 원인 분석" subtitle="설비 다운타임 원인을 대화형으로 확인하세요." date="2026.09.18" />

      <div className="ai-chat-grid">
        <section className="ai-chat-panel">
          <div className="ai-chat-intro">
            <span className="ai-chat-avatar">
              <IconRobot />
            </span>
            <div>
              <h3>MESTORY 어시스턴트</h3>
              <p>MESTORY의 AI가 설비 데이터를 분석하여 원인을 알려드립니다.</p>
            </div>
          </div>

          <div className="ai-chat-messages">
            {!hydrating && turns.length === 0 && (
              <>
                <p className="helper-text">예: "EQ-021 프레스 라인의 다운타임 원인을 요약해줘"처럼 물어보세요.</p>
                {reviewNeeded.length > 0 && (
                  <div className="ai-suggestions">
                    <span className="ai-suggestions-label">확인이 필요한 설비</span>
                    <div className="ai-suggestion-list">
                      {reviewNeeded.map((item) => (
                        <button
                          key={item.equipment_id}
                          type="button"
                          className={`ai-suggestion-button ${item.status === "정지" ? "ai-suggestion-stop" : "ai-suggestion-warn"}`}
                          disabled={loading}
                          onClick={() => void submitQuestion(`${item.equipment_id} ${item.equipment_type} 다운타임 원인을 분석해줘`)}
                        >
                          {item.status === "정지" ? <IconStopCircle /> : <IconTriangleWarning />}
                          {item.equipment_id} {item.equipment_type}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}

            {turns.map((turn, index) =>
              turn.role === "user" ? (
                <div key={index}>
                  <div className="ai-message ai-message-user">
                    <div className="ai-bubble ai-bubble-user">{turn.content}</div>
                    <span className="ai-chat-avatar ai-chat-avatar-user">
                      <IconUser />
                    </span>
                  </div>
                  <span className="ai-chat-time ai-chat-time-user">{formatTime(turn.created_at)}</span>
                </div>
              ) : (
                <div key={index}>
                  <div className="ai-message">
                    <span className="ai-chat-avatar">
                      <IconRobot />
                    </span>
                    <div className="ai-bubble ai-bubble-answer">
                      <p className="ai-answer-headline">{turn.content}</p>
                      {turn.report && (
                        <dl className="ai-answer-details">
                          <div className="ai-answer-row">
                            <dt>기간</dt>
                            <dd>{turn.report.period}</dd>
                          </div>
                          <div className="ai-answer-row">
                            <dt>라인 · 설비</dt>
                            <dd>{turn.report.line_id} · {turn.report.equipment_id}</dd>
                          </div>
                          <div className="ai-answer-row">
                            <dt>분석 참고 사항</dt>
                            <dd>{turn.report.confidence_note}</dd>
                          </div>
                        </dl>
                      )}
                      {turn.report && (
                        <Link href={`/reports/${turn.report.id}`} className="primary-button-inline ai-report-button">
                          <IconReport /> 상세 리포트 보기 ›
                        </Link>
                      )}
                    </div>
                  </div>
                  <span className="ai-chat-time">{formatTime(turn.created_at)}</span>
                </div>
              ),
            )}

            {loading && (
              <div className="ai-message">
                <span className="ai-chat-avatar">
                  <IconRobot />
                </span>
                <div className="ai-bubble ai-bubble-answer">
                  <span className="spinner" /> 분석 중입니다...
                </div>
              </div>
            )}
            {error && <p className="form-error" role="alert">{error}</p>}
            <div ref={messagesEndRef} />
          </div>

          <form className="ai-chat-input-row" onSubmit={handleSubmit}>
            <input
              type="text"
              placeholder="질문을 입력하세요"
              aria-label="AI에게 질문하기"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={loading}
            />
            <button type="submit" className="ai-send-button" aria-label="전송" disabled={loading || !input.trim()}>
              <IconSend />
            </button>
          </form>
        </section>

        <aside className="ai-sidebar">
          {lastReport ? (
            <>
              <InsightPanel report={lastReport} />
              <CauseBreakdown causes={lastReport.causes} />
            </>
          ) : (
            <section className="ai-summary-card">
              <p className="helper-text">질문을 하면 분석 결과 요약이 여기에 표시됩니다.</p>
            </section>
          )}
        </aside>
      </div>
    </main>
  );
}
