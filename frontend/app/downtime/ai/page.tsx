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
import {
  IconChevronRight, IconPlus, IconReport, IconRobot, IconSend, IconStopCircle,
  IconTriangleWarning, IconUser,
} from "../../../components/icons";
import { ReportApiError, createReportWithId, getChatHistory, listChatSessions, listEquipment } from "../../../lib/api";
import { reportScope } from "../../../lib/labels";
import type { ChatSessionSummary, ChatTurn, DowntimeReport, SavedReport } from "../../../types/report";
import type { EquipmentSummaryItem } from "../../../types/equipment";

const SESSION_STORAGE_KEY = "mestory:ai-chat-session-id";

// crypto.randomUUID는 HTTPS/localhost 같은 보안 컨텍스트에서만 있다 — http://사내IP 로 열면
// 정의되지 않아 화면이 통째로 깨지므로 대체값을 둔다.
function makeSessionId(): string {
  return typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `session-${Date.now()}`;
}

function loadOrCreateSessionId(): string {
  if (typeof window === "undefined") return "";
  const existing = window.localStorage.getItem(SESSION_STORAGE_KEY);
  if (existing) return existing;
  const created = makeSessionId();
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

// 방금 나온 리포트를 근거로 "이어서 물어볼 만한" 질문을 만든다 — 지어낸 예시가 아니라
// 실제 causes 값(에러코드·확정 여부)에서 뽑는다.
function buildFollowUps(report: DowntimeReport): { label: string; question: string }[] {
  const suggestions: { label: string; question: string }[] = [];
  const bySeverity = [...report.causes].sort((a, b) => {
    const rank: Record<string, number> = { 중대: 0, 보통: 1, 경미: 2, "판정 불가": 3 };
    return (rank[a.severity] ?? 3) - (rank[b.severity] ?? 3);
  });
  const top = bySeverity[0];
  // 에러코드가 비어 있는 원인("판정 불가")은 " 조치 방법…"처럼 이름 없는 버튼이 되므로 제외한다.
  if (top?.error_code?.trim()) {
    suggestions.push({
      label: `${top.error_code} 조치 방법 더 알려줘`,
      question: `${top.error_code} 원인에 대한 구체적인 조치 방법을 더 자세히 알려줘`,
    });
  }
  if (report.causes.some((c) => !c.is_confirmed)) {
    suggestions.push({
      label: "미확정 원인 더 설명해줘",
      question: "잠정 판단(미확정)으로 남은 원인들을 왜 확정하지 못했는지 더 자세히 설명해줘",
    });
  }
  if (report.equipment_id && report.equipment_id !== "전체 설비") {
    suggestions.push({
      label: "최근 정비 이력 보여줘",
      question: `${report.equipment_id}의 최근 정비 이력을 보여줘`,
    });
  }
  return suggestions;
}

export default function AiAnalysisChatPage() {
  const [sessionId, setSessionId] = useState("");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [hydrating, setHydrating] = useState(true);
  const [reviewNeeded, setReviewNeeded] = useState<EquipmentSummaryItem[]>([]);
  const [allEquipment, setAllEquipment] = useState<EquipmentSummaryItem[]>([]);
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  // 지금 화면에 보이는 세션. 응답이 늦게 도착했을 때 "그 사이 다른 대화로 옮겼는지" 판단하는 기준이다.
  const activeSessionRef = useRef("");

  function refreshSessions() {
    listChatSessions()
      .then(setSessions)
      .catch((cause) => {
        setError(cause instanceof Error ? cause.message : "세션 목록을 불러오지 못했습니다.");
      });
  }

  function loadSession(id: string) {
    activeSessionRef.current = id;
    setSessionId(id);
    window.localStorage.setItem(SESSION_STORAGE_KEY, id);
    setHydrating(true);
    setError("");
    // 세션을 빠르게 갈아타면 먼저 요청한 대화 기록이 늦게 도착해 현재 화면을 덮어쓸 수 있다.
    const isCurrent = () => activeSessionRef.current === id;
    getChatHistory(id)
      .then((history) => isCurrent() && setTurns(history))
      .catch((cause) => {
        if (isCurrent()) {
          setError(cause instanceof Error ? cause.message : "대화 기록을 불러오지 못했습니다.");
        }
      })
      .finally(() => isCurrent() && setHydrating(false));
  }

  function startNewSession() {
    if (loading) return;
    setTurns([]);
    loadSession(makeSessionId());
  }

  useEffect(() => {
    loadSession(loadOrCreateSessionId());
    refreshSessions();
  }, []);

  // 사용자가 57대 설비 상태를 일일이 파악할 수 없으니, 확인이 필요한(정상이 아닌)
  // 설비만 추려 버튼으로 먼저 보여준다 — 설비관리 화면과 같은 status 값을 그대로 쓴다.
  useEffect(() => {
    listEquipment()
      .then((items) => {
        setAllEquipment(items);
        setReviewNeeded(items.filter((item) => item.status !== "정상"));
      })
      .catch((cause) => {
        setError(cause instanceof Error ? cause.message : "설비 상태를 불러오지 못했습니다.");
      });
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, loading]);

  const lastReport: SavedReport | undefined = [...turns].reverse().find((t) => t.report)?.report;
  const lastTurn = turns[turns.length - 1];
  const followUps = !loading && lastTurn?.role === "assistant" && lastReport ? buildFollowUps(lastReport) : [];

  async function submitQuestion(rawQuestion: string) {
    const question = rawQuestion.trim();
    if (!question || loading || !sessionId) return;

    const askedSession = sessionId;
    setInput("");
    setError("");
    const askedAt = new Date().toISOString();
    setTurns((prev) => [...prev, { role: "user", content: question, created_at: askedAt }]);
    setLoading(true);

    try {
      const { report, reportId } = await createReportWithId({ session_id: askedSession, message: question });
      refreshSessions();
      // 분석하는 동안 다른 대화로 옮겼다면 그 대화 화면에 이 답변을 끼워 넣지 않는다
      // (답변은 이미 서버에 저장됐으므로 원래 대화로 돌아오면 보인다).
      if (activeSessionRef.current !== askedSession) return;
      const savedReport: SavedReport | undefined = reportId
        ? { ...report, id: reportId, session_id: askedSession, created_at: new Date().toISOString() }
        : undefined;
      setTurns((prev) => [
        ...prev,
        { role: "assistant", content: report.recommended_action, created_at: new Date().toISOString(), report: savedReport },
      ]);
    } catch (cause) {
      if (activeSessionRef.current === askedSession) {
        // 422는 "설비·라인을 알려 달라" 같은 안내 문장이 detail에 들어 있다 — 그대로 보여 준다.
        const detail = cause instanceof ReportApiError && cause.status === 422 && typeof (cause.body as { detail?: unknown })?.detail === "string"
          ? (cause.body as { detail: string }).detail
          : null;
        setError(detail ?? (cause instanceof Error ? cause.message : "알 수 없는 오류가 발생했습니다."));
      }
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
      <Topbar title="AI 원인 분석" subtitle="설비 다운타임 원인을 대화형으로 확인하세요." />

      <div className="ai-chat-grid">
        <aside className="ai-session-list">
          <button type="button" className="ai-session-new" onClick={startNewSession}>
            <IconPlus /> 새 대화 시작
          </button>
          <div className="ai-session-items">
            {sessions.length === 0 && !error && <p className="helper-text">저장된 대화가 없습니다.</p>}
            {sessions.map((s) => (
              <button
                key={s.session_id}
                type="button"
                className={`ai-session-item ${s.session_id === sessionId ? "ai-session-item-active" : ""}`}
                disabled={loading}
                onClick={() => loadSession(s.session_id)}
              >
                <span className="ai-session-item-title">{s.title || "새 대화"}</span>
                <span className="ai-session-item-meta">{formatTime(s.last_active)}</span>
              </button>
            ))}
          </div>
        </aside>

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
            {!hydrating && turns.length === 0 && !error && (
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
                            <dd>{reportScope(turn.report, allEquipment)}</dd>
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
            {followUps.length > 0 && (
              <div className="ai-suggestions ai-followups">
                <span className="ai-suggestions-label">이어서 물어보기</span>
                <div className="ai-suggestion-list">
                  {followUps.map((f) => (
                    <button
                      key={f.label}
                      type="button"
                      className="ai-suggestion-button ai-suggestion-followup"
                      disabled={loading}
                      onClick={() => void submitQuestion(f.question)}
                    >
                      <IconChevronRight /> {f.label}
                    </button>
                  ))}
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
