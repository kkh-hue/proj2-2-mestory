// AI 원인 분석 — 대화형 화면 목업 (대시보드 "AI 원인 분석 요약" 옆 AI 배지에서 진입).
// 다른 목업 화면과 같은 이유로 정적 값을 씀 — 실제로는 이 대화가 backend POST /report로 이어져야 함.
// 입력창의 onSubmit 핸들러 때문에 Client Component여야 한다(Server Component는 이벤트 핸들러를 못 씀).
"use client";

import Topbar from "../../../components/Topbar";
import {
  IconClock,
  IconHourglass,
  IconLightbulb,
  IconReport,
  IconRobot,
  IconSend,
  IconShield,
  IconTarget,
  IconTriangleWarning,
  IconUser,
} from "../../../components/icons";
import { aiSummary } from "../../../lib/mockDashboard";
import { aiAnswer, recommendedActions, relatedEquipment, userQuestion } from "../../../lib/mockAiChat";

const ROW_ICON = { clock: IconClock, warning: IconTriangleWarning, hourglass: IconHourglass, shield: IconShield };

export default function AiAnalysisChatPage() {
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
              <h3>AI 원인 어시스턴트</h3>
              <p>MESTORY의 AI가 설비 데이터를 분석하여 원인을 알려드립니다.</p>
            </div>
          </div>

          <div className="ai-chat-messages">
            <div className="ai-message ai-message-user">
              <div className="ai-bubble ai-bubble-user">{userQuestion.text}</div>
              <span className="ai-chat-avatar ai-chat-avatar-user">
                <IconUser />
              </span>
            </div>
            <span className="ai-chat-time ai-chat-time-user">{userQuestion.time}</span>

            <div className="ai-message">
              <span className="ai-chat-avatar">
                <IconRobot />
              </span>
              <div className="ai-bubble ai-bubble-answer">
                <p className="ai-answer-headline">
                  주요 원인은 <strong>{aiAnswer.causeHighlight}</strong>입니다.
                </p>
                <dl className="ai-answer-details">
                  {aiAnswer.detailRows.map((row) => {
                    const Icon = ROW_ICON[row.icon];
                    return (
                      <div className="ai-answer-row" key={row.label}>
                        <dt>
                          <Icon /> {row.label}
                        </dt>
                        <dd>{row.value}</dd>
                      </div>
                    );
                  })}
                </dl>
                <button type="button" className="primary-button-inline ai-report-button">
                  <IconReport /> 상세 리포트 보기 ›
                </button>
              </div>
            </div>
            <span className="ai-chat-time">{aiAnswer.time}</span>
          </div>

          <form className="ai-chat-input-row" onSubmit={(e) => e.preventDefault()}>
            <input type="text" placeholder="질문을 입력하세요" aria-label="AI에게 질문하기" />
            <button type="submit" className="ai-send-button" aria-label="전송">
              <IconSend />
            </button>
          </form>
        </section>

        <aside className="ai-sidebar">
          <section className="ai-summary-card">
            <div className="ai-summary-head">
              <h3>분석 요약</h3>
            </div>
            <div className="ai-primary-cause">
              <div className="ai-primary-cause-text">
                <span className="ai-tag">
                  <IconTriangleWarning /> 주요 원인
                </span>
                <div className="ai-cause-name">{aiSummary.cause}</div>
              </div>
              <div className="ai-confidence">
                <span>신뢰도</span>
                <strong>{aiSummary.confidence}%</strong>
              </div>
            </div>
            <div className="ai-breakdown">
              <h4>원인별 비중</h4>
              <ul>
                {aiSummary.breakdown.map((item) => (
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

          <section className="ai-action-card">
            <div className="ai-summary-head">
              <h3>
                <IconLightbulb className="insight-title-icon" /> 권장 조치 사항
              </h3>
            </div>
            <ul className="ai-action-list">
              {recommendedActions.map((action) => (
                <li key={action}>
                  <span className="ai-action-check">
                    <IconShield />
                  </span>
                  {action}
                </li>
              ))}
            </ul>
          </section>

          <section className="ai-related-card">
            <div className="ai-summary-head">
              <h3>
                <IconTarget className="insight-title-icon" /> 관련 설비
              </h3>
            </div>
            <div className="ai-related-row">
              <span className="events-id">{relatedEquipment.id}</span>
              <span className="ai-related-name">{relatedEquipment.name}</span>
              <span className="severity-badge severity-badge-critical">{relatedEquipment.severity}</span>
            </div>
          </section>
        </aside>
      </div>
    </main>
  );
}
