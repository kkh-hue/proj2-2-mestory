import Link from "next/link";
import { IconSparkle } from "./icons";
import TruncatedTextPopover from "./TruncatedTextPopover";
import type { SavedReport } from "../types/report";

// 개별 사건 발생 건수·시간은 출력 계약에 없는 값이라 지어내지 않는다 —
// CauseBreakdown과 같은 원칙으로, 심각도 기준 막대 길이만 쓴다.
const SEVERITY_WIDTH: Record<string, number> = { "중대": 90, "보통": 60, "경미": 30, "판정 불가": 12 };

export default function AiSummaryCard({ report }: { report: SavedReport | null }) {
  if (!report) {
    return (
      <section className="ai-summary-card">
        <div className="ai-summary-head">
          <h3>AI 원인 분석 요약</h3>
          <Link href="/downtime/ai" className="ai-badge" aria-label="AI 원인 분석 대화형 화면 열기">
            <IconSparkle />
          </Link>
        </div>
        <p className="helper-text">아직 분석된 리포트가 없습니다. "AI 원인분석" 화면에서 질문해보세요.</p>
      </section>
    );
  }

  const topCause = report.causes[0];
  const confirmedRatio = report.causes.length
    ? Math.round((report.causes.filter((c) => c.is_confirmed).length / report.causes.length) * 100)
    : null;

  return (
    <section className="ai-summary-card">
      <div className="ai-summary-head">
        <h3>AI 원인 분석 요약</h3>
        <Link href="/downtime/ai" className="ai-badge" aria-label="AI 원인 분석 대화형 화면 열기">
          <IconSparkle />
        </Link>
      </div>

      <div className="ai-primary-cause">
        <div className="ai-primary-cause-text">
          <span className="ai-tag">주요 원인</span>
          <div className="ai-cause-name">{topCause?.description ?? report.recommended_action}</div>
          <p className="ai-cause-desc">{report.confidence_note}</p>
        </div>
        {confirmedRatio !== null && (
          <div className="ai-confidence">
            <span>확정 비율</span>
            <strong>{confirmedRatio}%</strong>
          </div>
        )}
      </div>

      {report.causes.length > 0 && (
        <div className="ai-breakdown">
          <h4>원인 목록 (심각도 기준)</h4>
          <ul>
            {report.causes.map((cause, index) => (
              <li key={`${cause.error_code}-${index}`}>
                <TruncatedTextPopover className="ai-breakdown-label" text={cause.description} />
                <span className="ai-breakdown-bar-track">
                  <span className="ai-breakdown-bar-fill" style={{ width: `${SEVERITY_WIDTH[cause.severity] ?? 12}%` }} />
                </span>
                <span className="ai-breakdown-percent">{cause.severity}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
