// 리포트 상세 (F-07) — AI 원인분석 화면의 "상세 리포트 보기"가 여기로 온다.
// 엑셀 다운로드는 의존성 추가 없이 CSV로 만든다 (엑셀이 CSV를 그대로 열 수 있고,
// xlsx 패키지는 npm 배포판에 고쳐지지 않은 취약점이 있어 쓰지 않는다).
// PDF 다운로드는 브라우저 인쇄(다른 프린터로 저장 → PDF)로 처리한다 — 별도 서버 렌더링 없이 바로 된다.
"use client";

import html2canvas from "html2canvas";
import jsPDF from "jspdf";
import { useEffect, useRef, useState } from "react";
import CauseBreakdown from "../../../components/CauseBreakdown";
import CauseDetailTable from "../../../components/CauseDetailTable";
import InsightPanel from "../../../components/InsightPanel";
import Topbar from "../../../components/Topbar";
import { IconDownload, IconMail, IconReport } from "../../../components/icons";
import { getReport, listEquipment, ReportApiError, sendReportEmail } from "../../../lib/api";
import { reportScope, reportTitle } from "../../../lib/labels";
import type { EquipmentSummaryItem } from "../../../types/equipment";
import { downloadCsv } from "../../../lib/reportCsv";
import { splitSentences, splitSteps } from "../../../lib/text";
import type { SavedReport } from "../../../types/report";

export default function ReportDetailPage({ params }: { params: { id: string } }) {
  const [report, setReport] = useState<SavedReport | null>(null);
  const [error, setError] = useState("");
  const [notFound, setNotFound] = useState(false);
  const [loading, setLoading] = useState(true);
  const [equipment, setEquipment] = useState<EquipmentSummaryItem[]>([]);
  const [equipmentError, setEquipmentError] = useState("");
  // 메일 보내기 (docs/specs/report-email.md). 툴바가 붐비지 않게 버튼을 누르면 입력칸이 펼쳐진다.
  const [emailOpen, setEmailOpen] = useState(false);
  const [emailTo, setEmailTo] = useState("");
  const [emailSending, setEmailSending] = useState(false);
  // 결과를 성공/실패로 나눠 들고 있는다 — 같은 자리에 색만 달리 보여주기 위해서다.
  const [emailResult, setEmailResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [pdfGenerating, setPdfGenerating] = useState(false);
  const [pdfError, setPdfError] = useState("");
  const reportContentRef = useRef<HTMLDivElement>(null);

  // 서버가 돌려준 상태 코드를 사람이 읽을 말로 바꾼다.
  // 서버 detail을 그대로 보여주지 않는 이유: 사용자가 할 수 있는 일을 알려줘야 하기 때문이다.
  function emailErrorMessage(cause: unknown): string {
    if (cause instanceof ReportApiError) {
      if (cause.status === 403) return "이 주소로는 보낼 수 없습니다. 관리자에게 수신 허용을 요청하세요.";
      if (cause.status === 404) return "리포트를 찾을 수 없습니다.";
      if (cause.status === 422) return "메일 주소 형식을 확인해 주세요.";
      if (cause.status === 502) return "메일 발송 서비스에 문제가 있습니다. 잠시 후 다시 시도해 주세요.";
      if (cause.status === 503) return "서버가 데이터베이스에 연결하지 못했습니다.";
      return "메일을 보내지 못했습니다. 다시 시도해 주세요.";
    }
    if (cause instanceof Error && cause.message.includes("초")) {
      return "응답이 너무 늦습니다. 잠시 후 다시 시도해 주세요.";
    }
    return "네트워크 연결을 확인해 주세요.";
  }

  async function handleSendEmail() {
    if (!report || emailSending || !emailTo.trim()) return;
    setEmailSending(true);
    setEmailResult(null);
    try {
      await sendReportEmail(report.id, emailTo.trim());
      setEmailResult({ ok: true, message: `${emailTo.trim()} 으로 보냈습니다.` });
      setEmailTo("");
    } catch (cause) {
      setEmailResult({ ok: false, message: emailErrorMessage(cause) });
    } finally {
      setEmailSending(false);
    }
  }

  function safePdfFileName(value: string) {
    return value
      .replace(/[<>:"/\\|?*\u0000-\u001F]/g, "-")
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 120) || "report";
  }

  async function handleDownloadPdf() {
    if (!report || pdfGenerating || !reportContentRef.current) return;
    setPdfGenerating(true);
    setPdfError("");

    try {
      const canvas = await html2canvas(reportContentRef.current, {
        backgroundColor: "#ffffff",
        scale: Math.min(window.devicePixelRatio || 1, 2),
        useCORS: true,
        ignoreElements: (element) => element.classList.contains("no-print"),
      });
      const pdf = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
      const pageWidth = 210;
      const pageHeight = 297;
      const margin = 10;
      const contentWidth = pageWidth - margin * 2;
      const contentHeight = (canvas.height * contentWidth) / canvas.width;
      const imageData = canvas.toDataURL("image/png");
      let remainingHeight = contentHeight;
      let position = margin;

      pdf.addImage(imageData, "PNG", margin, position, contentWidth, contentHeight);
      remainingHeight -= pageHeight - margin * 2;
      while (remainingHeight > 0) {
        position = margin - (contentHeight - remainingHeight);
        pdf.addPage();
        pdf.addImage(imageData, "PNG", margin, position, contentWidth, contentHeight);
        remainingHeight -= pageHeight - margin * 2;
      }

      const reportName = safePdfFileName(report.equipment_id || "report");
      const period = safePdfFileName(report.period);
      pdf.save(`MESTORY_${reportName}_${period}.pdf`);
    } catch (cause) {
      console.error("PDF 생성 실패", cause);
      setPdfError("PDF를 생성하지 못했습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      setPdfGenerating(false);
    }
  }

  useEffect(() => {
    listEquipment()
      .then(setEquipment)
      .catch((cause) => setEquipmentError(cause instanceof Error ? cause.message : "설비 목록을 불러오지 못했습니다."));
    getReport(params.id)
      .then(setReport)
      .catch((cause) => {
        if (cause instanceof ReportApiError && cause.status === 404) {
          setNotFound(true);
          setError("리포트를 찾을 수 없습니다.\n삭제되었거나 존재하지 않는 리포트입니다.");
          return;
        }
        if (cause instanceof ReportApiError || (cause instanceof Error && cause.message.includes("10초"))) {
          setError("리포트를 불러오지 못했습니다.\n다시 시도해 주세요.");
        } else {
          setError("네트워크 연결을 확인해 주세요.");
        }
      })
      .finally(() => setLoading(false));
  }, [params.id]);

  return (
    <main className="page" ref={reportContentRef}>
      <Topbar
        title={report ? reportTitle(report, equipment) : "리포트 상세"}
        subtitle={report ? `${reportScope(report, equipment)} · ${report.period}` : "불러오는 중..."}
        action={
          report ? (
            <div className="report-detail-actions">
              <button
                type="button"
                className="secondary-button no-print"
                onClick={() => setEmailOpen((open) => !open)}
                aria-expanded={emailOpen}
              >
                <IconMail /> 메일 보내기
              </button>
              <button type="button" className="secondary-button no-print" onClick={() => downloadCsv(report)}>
                <IconDownload /> 엑셀 다운로드
              </button>
              <button type="button" className="primary-button-inline no-print" onClick={handleDownloadPdf} disabled={pdfGenerating}>
                <IconReport /> {pdfGenerating ? "PDF 생성 중..." : "PDF로 저장"}
              </button>
            </div>
          ) : undefined
        }
      />

      {loading && (
        <section className="status-card status-loading" aria-live="polite">
          <span className="spinner" /> 리포트를 불러오는 중입니다.
        </section>
      )}

      {!loading && (error || equipmentError) && (
        <section className="status-card status-error" role="alert">
          {notFound ? (
            <span style={{ whiteSpace: "pre-line" }}>{error}</span>
          ) : (
            <>
              <strong>리포트를 불러오지 못했습니다.</strong>
              <span>{error || equipmentError}</span>
            </>
          )}
        </section>
      )}

      {!loading && pdfError && <p className="form-error no-print" role="alert">{pdfError}</p>}

      {!loading && !error && report && (
        <>
          {equipmentError && (
            <p className="form-error" role="status">
              설비 정보를 불러오지 못했습니다. {equipmentError}
            </p>
          )}

          {/* 메일 보내기. 인쇄(PDF 저장)할 때는 빠지도록 no-print를 붙인다. */}
          {emailOpen && (
            <section className="email-panel no-print">
              <form
                className="email-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  handleSendEmail();
                }}
              >
                <label className="email-label" htmlFor="report-email-to">
                  받는 사람 메일 주소
                </label>
                <div className="email-row">
                  <input
                    id="report-email-to"
                    type="email"
                    className="email-input"
                    placeholder="name@example.com"
                    value={emailTo}
                    onChange={(event) => setEmailTo(event.target.value)}
                    disabled={emailSending}
                    autoComplete="email"
                  />
                  <button
                    type="submit"
                    className="primary-button-inline"
                    disabled={emailSending || !emailTo.trim()}
                  >
                    {emailSending ? "보내는 중..." : "보내기"}
                  </button>
                </div>
              </form>
              {/* 허용 목록은 화면에 뿌리지 않는다 — 서버 보안 설정이라 노출하지 않는다. */}
              <p className="email-hint">
                서버에 등록된 주소로만 보낼 수 있습니다. 메일에는 이 리포트 요약과 상세 페이지 링크가 담깁니다.
              </p>
              {emailResult && (
                <p className={emailResult.ok ? "email-result-ok" : "email-result-error"} role="status">
                  {emailResult.message}
                </p>
              )}
            </section>
          )}
          <div className="dashboard-grid">
            <CauseBreakdown causes={report.causes} />
            <InsightPanel report={report} />
          </div>
          <CauseDetailTable causes={report.causes} />
          {/* 한 덩어리로 오는 긴 서술을 항목/문장 단위로 끊어 그린다 (lib/text.ts).
              권장 조치는 "1) 2) 3)" 번호 단위, 참고 사항은 문장 단위가 읽기 좋다. */}
          <section className="recommendation-panel">
            <h3>권장 조치</h3>
            <ul className="panel-lines">
              {splitSteps(report.recommended_action).map((line, index) => (
                <li key={index}>{line}</li>
              ))}
            </ul>
          </section>
          <section className="note-panel">
            <h3>분석 참고 사항</h3>
            <ul className="panel-lines">
              {splitSentences(report.confidence_note).map((line, index) => (
                <li key={index}>{line}</li>
              ))}
            </ul>
          </section>
        </>
      )}
    </main>
  );
}
