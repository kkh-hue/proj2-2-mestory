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
  IconChevronRight, IconPaperclip, IconPlus, IconReport, IconRobot, IconSend, IconStopCircle,
  IconTriangleWarning, IconUser,
} from "../../../components/icons";
import { ReportApiError, createReportWithId, getChatHistory, listChatSessions, listEquipment } from "../../../lib/api";
import { todayKst } from "../../../lib/date";
import { useLiveTick } from "../../../lib/useLiveTick";
import { reportScope } from "../../../lib/labels";
import { splitSentences } from "../../../lib/text";
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

// ── 이미지 첨부 (docs/specs/multimodal-frontend.md) ───────────────────────
// backend/main.py의 MAX_IMAGES · MAX_IMAGE_BYTES · MAX_TOTAL_IMAGE_BYTES ·
// ALLOWED_IMAGE_SUBTYPES와 같은 값이다. 한쪽만 고치면 화면을 통과한 파일이
// 서버에서 422로 튕긴다 — 반드시 같이 고칠 것.
const MAX_IMAGES = 3;
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
const MAX_TOTAL_IMAGE_BYTES = 10 * 1024 * 1024;
const ALLOWED_IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp"];

// 첨부한 사진 1장. bytes를 들고 있는 이유는 합계 용량을 매번 다시 재지 않기 위해서다.
type Attachment = { name: string; bytes: number; dataUrl: string };

// images는 이제 백엔드 계약(types/report.ts의 ChatTurn)에 들어가 있다.
// 방금 올린 사진은 로컬 상태로, 새로고침 뒤에는 서버가 돌려준 썸네일로 같은 자리에 그려진다
// (docs/specs/chat-image-persistence.md). LLM 대화 맥락에는 여전히 들어가지 않는다.
type ChatTurnView = ChatTurn;

function megabytes(bytes: number): string {
  return (bytes / (1024 * 1024)).toFixed(1);
}

// 사진 파일을 data URL(긴 글자열)로 바꾼다. JSON에는 그림을 그대로 담을 수 없어서
// 글자로 번역해 보낸다. FileReader는 비동기라 Promise로 감싼다.
function readAsDataUrl(file: File): Promise<Attachment> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve({ name: file.name, bytes: file.size, dataUrl: String(reader.result) });
    reader.onerror = () => reject(new Error(file.name));
    reader.readAsDataURL(file);
  });
}

export default function AiAnalysisChatPage() {
  const [sessionId, setSessionId] = useState("");
  const [turns, setTurns] = useState<ChatTurnView[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  // 확대해서 보고 있는 첨부 사진. null이면 닫힌 상태다.
  const [zoomedImage, setZoomedImage] = useState<string | null>(null);
  const [hydrating, setHydrating] = useState(true);
  const [reviewNeeded, setReviewNeeded] = useState<EquipmentSummaryItem[]>([]);
  const [allEquipment, setAllEquipment] = useState<EquipmentSummaryItem[]>([]);
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  // 설비 목록 버튼은 이 날짜 기준 상태를 본다 — 다른 화면(대시보드·설비현황·알림센터)과 같은 기준.
  const [asOf, setAsOf] = useState(todayKst());
  const equipmentTick = useLiveTick(asOf);
  // 아직 보내지 않은 첨부 사진. 전송을 시도하면 비운다.
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  // 기본 파일 선택 버튼은 디자인이 팀 스타일과 어긋나 숨겨 두고, 클립 버튼이 대신 눌러 준다.
  const fileInputRef = useRef<HTMLInputElement>(null);
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
    // 대화를 옮기면 아직 보내지 않은 첨부도 비운다 — 다른 대화의 근거로 딸려가면 안 된다.
    setAttachments([]);
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

  // 확대 보기는 ESC로도 닫는다. 열려 있을 때만 리스너를 달아 둔다.
  useEffect(() => {
    if (!zoomedImage) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setZoomedImage(null);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [zoomedImage]);

  // 사용자가 57대 설비 상태를 일일이 파악할 수 없으니, 확인이 필요한(정상이 아닌)
  // 설비만 추려 버튼으로 먼저 보여준다 — 설비관리 화면과 같은 status 값을, 같은 날짜(asOf)
  // 기준으로 그대로 쓴다. 오늘이면 useLiveTick으로 1분마다 조용히 다시 불러온다.
  useEffect(() => {
    let cancelled = false;
    listEquipment(asOf)
      .then((items) => {
        if (cancelled) return;
        setAllEquipment(items);
        setReviewNeeded(items.filter((item) => item.status !== "정상"));
      })
      .catch((cause) => {
        if (!cancelled) setError(cause instanceof Error ? cause.message : "설비 상태를 불러오지 못했습니다.");
      });
    return () => {
      cancelled = true;
    };
  }, [asOf, equipmentTick]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, loading]);

  const lastReport: SavedReport | undefined = [...turns].reverse().find((t) => t.report)?.report;
  const lastTurn = turns[turns.length - 1];
  const followUps = !loading && lastTurn?.role === "assistant" && lastReport ? buildFollowUps(lastReport) : [];

  // 고른 파일을 검사해서 통과한 것만 첨부 목록에 넣는다.
  // 서버도 같은 검사를 하지만, 여기서 먼저 막아야 5MB를 헛되이 올린 뒤 거절당하지 않는다.
  function handleFilesPicked(event: React.ChangeEvent<HTMLInputElement>) {
    const picked = Array.from(event.target.files ?? []);
    // 같은 파일을 연달아 골라도 onChange가 다시 불리도록 값을 비운다.
    event.target.value = "";
    if (picked.length === 0) return;

    // 장수 초과는 앞 몇 장만 취하지 않고 전부 거부한다 — 어느 장이 빠졌는지 모르는 쪽이 더 나쁘다.
    if (attachments.length + picked.length > MAX_IMAGES) {
      setError(`이미지는 최대 ${MAX_IMAGES}장까지 첨부할 수 있습니다.`);
      return;
    }

    let total = attachments.reduce((sum, item) => sum + item.bytes, 0);
    const accepted: File[] = [];
    const rejected: string[] = [];
    let typeRejected = false;

    for (const file of picked) {
      if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
        rejected.push(`${file.name}(지원하지 않는 형식)`);
        typeRejected = true;
        continue;
      }
      if (file.size > MAX_IMAGE_BYTES) {
        rejected.push(`${file.name}(${megabytes(file.size)}MB — 한 장 최대 ${MAX_IMAGE_BYTES / (1024 * 1024)}MB)`);
        continue;
      }
      if (total + file.size > MAX_TOTAL_IMAGE_BYTES) {
        rejected.push(`${file.name}(합계 ${MAX_TOTAL_IMAGE_BYTES / (1024 * 1024)}MB 초과)`);
        continue;
      }
      total += file.size;
      accepted.push(file);
    }

    // 아이폰 기본 사진은 HEIC라 accept 속성으로 걸러도 "모든 파일"로 바꿔 고를 수 있다.
    const heicHint = typeRejected ? " png·jpg·webp만 첨부할 수 있습니다. 아이폰 사진은 png나 jpg로 저장해 주세요." : "";
    setError(rejected.length > 0 ? `첨부하지 못한 파일: ${rejected.join(", ")}.${heicHint}` : "");
    if (accepted.length === 0) return;

    Promise.all(accepted.map(readAsDataUrl))
      .then((added) => setAttachments((prev) => [...prev, ...added]))
      .catch((cause) => setError(`이미지를 읽지 못했습니다: ${cause instanceof Error ? cause.message : "알 수 없는 파일"}`));
  }

  function removeAttachment(index: number) {
    setAttachments((prev) => prev.filter((_, i) => i !== index));
  }

  async function submitQuestion(rawQuestion: string, dateRange?: { date_from: string; date_to: string }) {
    const question = rawQuestion.trim();
    if (!question || loading || !sessionId) return;

    const askedSession = sessionId;
    // 전송 시도 후에는 성공·실패와 무관하게 첨부를 비운다. 남겨 두면 다음 질문에 또 붙는다.
    const sentImages = attachments.map((item) => item.dataUrl);
    setAttachments([]);
    setInput("");
    setError("");
    const askedAt = new Date().toISOString();
    setTurns((prev) => [
      ...prev,
      { role: "user", content: question, created_at: askedAt, images: sentImages.length > 0 ? sentImages : undefined },
    ]);
    setLoading(true);

    try {
      const { report, reportId } = await createReportWithId({
        session_id: askedSession,
        message: question,
        // 첨부가 없으면 아예 넣지 않는다 — 이미지 없는 기존 요청 경로를 그대로 탄다.
        ...(sentImages.length > 0 ? { images: sentImages } : {}),
        ...dateRange,
      });
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
      <Topbar
        title="AI 원인 분석"
        subtitle="설비 다운타임 원인을 대화형으로 확인하세요."
        date={asOf}
        onDateChange={setAsOf}
      />

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
                    <span className="ai-suggestions-label">{asOf} 기준 확인이 필요한 설비</span>
                    <div className="ai-suggestion-list">
                      {reviewNeeded.map((item) => (
                        <button
                          key={item.equipment_id}
                          type="button"
                          className={`ai-suggestion-button ${item.status === "정지" ? "ai-suggestion-stop" : "ai-suggestion-warn"}`}
                          disabled={loading}
                          // 버튼이 보여준 날짜와 실제 분석 기간이 어긋나지 않도록 같은 날짜를 그대로 넘긴다
                          // (안 넘기면 backend가 기간을 "전체"로 잡는다).
                          onClick={() =>
                            void submitQuestion(`${item.equipment_id} ${item.equipment_type} 다운타임 원인을 분석해줘`, {
                              date_from: asOf,
                              date_to: asOf,
                            })
                          }
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
                    <div className="ai-bubble ai-bubble-user">
                      {turn.content}
                      {/* 방금 올린 사진만 보인다 — 서버 대화 기록에는 저장되지 않아 새로고침하면 사라진다 */}
                      {turn.images && turn.images.length > 0 && (
                        <div className="ai-bubble-images">
                          {turn.images.map((src, imageIndex) => (
                            // 말풍선 크기로는 화면 속 글씨를 읽을 수 없어, 눌러서 크게 보게 한다
                            <button
                              key={imageIndex}
                              type="button"
                              className="ai-bubble-thumb"
                              onClick={() => setZoomedImage(src)}
                              aria-label={`첨부 이미지 ${imageIndex + 1} 크게 보기`}
                            >
                              {/* eslint-disable-next-line @next/next/no-img-element */}
                              <img src={src} alt={`첨부 이미지 ${imageIndex + 1}`} />
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
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
                      {/* 답변 요약도 여러 문장이 한 덩어리로 온다 — 문장마다 끊어 그린다 */}
                      <div className="ai-answer-headline">
                        {splitSentences(turn.content).map((line, lineIndex) => (
                          <p key={lineIndex}>{line}</p>
                        ))}
                      </div>
                      {turn.report && (
                        <dl className="ai-answer-details">
                          {/* 이미지를 올린 사람이 가장 먼저 확인하려는 값이라 맨 앞에 둔다.
                              읽어낸 것이 없으면 빈 칸을 남기지 않고 행 자체를 그리지 않는다. */}
                          {turn.report.used_image && turn.report.visual_findings && turn.report.visual_findings.length > 0 && (
                            <div className="ai-answer-row ai-answer-row-block">
                              <dt>이미지에서 확인한 것</dt>
                              <dd>
                                <ul className="ai-visual-findings">
                                  {turn.report.visual_findings.map((finding, findingIndex) => (
                                    <li key={findingIndex}>{finding}</li>
                                  ))}
                                </ul>
                              </dd>
                            </div>
                          )}
                          <div className="ai-answer-row">
                            <dt>기간</dt>
                            <dd>{turn.report.period}</dd>
                          </div>
                          <div className="ai-answer-row">
                            <dt>라인 · 설비</dt>
                            <dd>{reportScope(turn.report, allEquipment)}</dd>
                          </div>
                          {/* 값이 수백 자라 가로 배치·오른쪽 정렬로는 읽을 수 없다 — 세로로 내린다 */}
                          <div className="ai-answer-row ai-answer-row-block">
                            <dt>분석 참고 사항</dt>
                            <dd>
                              <ul className="panel-lines">
                                {splitSentences(turn.report.confidence_note).map((line, lineIndex) => (
                                  <li key={lineIndex}>{line}</li>
                                ))}
                              </ul>
                            </dd>
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

          {attachments.length > 0 && (
            <div className="ai-attach-row">
              {attachments.map((item, attachIndex) => (
                <span key={`${item.name}-${attachIndex}`} className="ai-attach-chip">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img className="ai-attach-thumb" src={item.dataUrl} alt="" />
                  <span className="ai-attach-name">{item.name}</span>
                  <button
                    type="button"
                    className="ai-attach-remove"
                    aria-label={`${item.name} 첨부 취소`}
                    disabled={loading}
                    onClick={() => removeAttachment(attachIndex)}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}

          <form className="ai-chat-input-row" onSubmit={handleSubmit}>
            {/* 실제 파일 선택 창을 여는 입력. 화면에는 숨기고 클립 버튼이 대신 누른다. */}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              multiple
              hidden
              onChange={handleFilesPicked}
            />
            <button
              type="button"
              className="ai-attach-button"
              aria-label="이미지 첨부"
              disabled={loading}
              onClick={() => fileInputRef.current?.click()}
            >
              <IconPaperclip />
            </button>
            <input
              type="text"
              placeholder="질문을 입력하세요"
              aria-label="AI에게 질문하기"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={loading}
            />
            {/* 이미지만으로는 보낼 수 없다 — backend가 설비·라인을 질문(message)에서 찾는다 */}
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

      {/* 첨부 사진 확대 보기. 배경 아무 곳이나 누르거나 ESC로 닫는다.
          button으로 만든 이유는 키보드로도 닫을 수 있어야 하기 때문이다. */}
      {zoomedImage && (
        <button
          type="button"
          className="image-viewer"
          onClick={() => setZoomedImage(null)}
          aria-label="확대 보기 닫기"
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={zoomedImage} alt="첨부 이미지 확대" />
          <span className="image-viewer-hint">아무 곳이나 누르거나 ESC를 눌러 닫습니다</span>
        </button>
      )}
    </main>
  );
}
