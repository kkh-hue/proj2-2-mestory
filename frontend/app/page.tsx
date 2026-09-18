// 대시보드 (F-07 확장). 담당: 강경희
// 요약 통계/추이/최근 이벤트는 백엔드 집계 엔드포인트가 아직 없어 mockDashboard.ts의 정적 값을 씁니다.
// 실제 리포트 생성(POST /report)은 "다운타임 분석" 탭(/downtime)에서 동작합니다.
import AiSummaryCard from "../components/AiSummaryCard";
import EventsTable from "../components/EventsTable";
import KpiCard from "../components/KpiCard";
import NewAnalysisModal from "../components/NewAnalysisModal";
import Topbar from "../components/Topbar";
import TrendChart from "../components/TrendChart";
import { aiSummary, kpiCards, needsReviewCount, recentEvents, trendSeries } from "../lib/mockDashboard";

export default function DashboardPage() {
  return (
    <main className="page">
      <Topbar
        title="대시보드"
        subtitle="AI가 설비 정지 원인을 빠르게 찾아드립니다."
        date="2026.09.18"
        action={<NewAnalysisModal />}
      />

      <section className="kpi-grid">
        {kpiCards.map((card) => (
          <KpiCard key={card.label} {...card} />
        ))}
      </section>

      <section className="dashboard-grid">
        <div className="trend-card">
          <div className="trend-card-head">
            <h3>라인별 다운타임 추이</h3>
            <ul className="trend-legend">
              {trendSeries.lines.map((line) => (
                <li key={line.key}>
                  <span className="trend-legend-dot" style={{ background: line.color }} />
                  {line.key}
                </li>
              ))}
            </ul>
          </div>
          <TrendChart labels={trendSeries.labels} lines={trendSeries.lines} maxY={trendSeries.maxY} />
        </div>

        <AiSummaryCard summary={aiSummary} />
      </section>

      <EventsTable rows={recentEvents} needsReviewCount={needsReviewCount} />
    </main>
  );
}
