import Link from "next/link";
import { IconSparkle } from "./icons";
import type { aiSummary as AiSummaryType } from "../lib/mockDashboard";

export default function AiSummaryCard({ summary }: { summary: typeof AiSummaryType }) {
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
          <div className="ai-cause-name">{summary.cause}</div>
          <p className="ai-cause-desc">{summary.description}</p>
        </div>
        <div className="ai-confidence">
          <span>신뢰도</span>
          <strong>{summary.confidence}%</strong>
        </div>
      </div>

      <div className="ai-breakdown">
        <h4>원인별 비중</h4>
        <ul>
          {summary.breakdown.map((item) => (
            <li key={item.label}>
              <span className="ai-breakdown-label">{item.label}</span>
              <span className="ai-breakdown-bar-track">
                <span className="ai-breakdown-bar-fill" style={{ width: `${item.percent}%` }} />
              </span>
              <span className="ai-breakdown-percent">{item.percent}%</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
