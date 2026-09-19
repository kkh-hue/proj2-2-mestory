// 대시보드 (F-07). backend GET /dashboard를 그대로 불러온다 (KPI·추이·최근 이벤트·최근 리포트 집계).
// 실제 리포트 생성(POST /report)은 "다운타임 분석" 탭(/downtime)에서 동작합니다.
"use client";

import { useEffect, useState } from "react";
import AiSummaryCard from "../components/AiSummaryCard";
import EventsTable from "../components/EventsTable";
import KpiCard, { type KpiCardData } from "../components/KpiCard";
import NewAnalysisModal from "../components/NewAnalysisModal";
import Topbar from "../components/Topbar";
import TrendChart from "../components/TrendChart";
import { getDashboard } from "../lib/api";
import type { DashboardSummary } from "../types/dashboard";

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

function formatToday() {
  const date = new Date();
  return `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, "0")}.${String(date.getDate()).padStart(2, "0")}`;
}

function formatTrendLabel(iso: string) {
  const date = new Date(iso);
  return `${String(date.getMonth() + 1).padStart(2, "0")}.${String(date.getDate()).padStart(2, "0")}\n(${WEEKDAYS[date.getDay()]})`;
}

function formatMinutes(min: number) {
  const hours = Math.floor(min / 60);
  const minutes = Math.round(min % 60);
  return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}분`;
}

function buildKpiCards(summary: DashboardSummary): KpiCardData[] {
  const { kpi } = summary;
  return [
    {
      label: "오늘 다운타임", value: formatMinutes(kpi.today_downtime_min), icon: "clock",
      delta: { ...kpi.downtime_delta, good: kpi.downtime_delta.direction === "down" },
    },
    {
      label: "분석 완료", value: `${kpi.reports_today}건`, icon: "check",
      delta: { ...kpi.reports_delta, good: kpi.reports_delta.direction === "up" },
    },
    {
      label: "평균 복구시간", value: `${Math.round(kpi.avg_recovery_min)}분`, icon: "timer",
      delta: { ...kpi.recovery_delta, good: kpi.recovery_delta.direction === "down" },
    },
    {
      label: "가동률", value: `${kpi.utilization_pct}%`, icon: "gauge",
      delta: { ...kpi.utilization_delta, good: kpi.utilization_delta.direction === "up" },
    },
  ];
}

const LINE_COLORS = ["var(--chart-a)", "var(--chart-b)", "var(--chart-c)", "#c9860f", "#2f9e5b"];

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getDashboard()
      .then(setSummary)
      .catch((cause) => setError(cause instanceof Error ? cause.message : "대시보드 데이터를 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, []);

  const needsReviewCount = summary?.recent_events.filter((e) => e.severity === "판정 불가").length ?? 0;

  return (
    <main className="page">
      <Topbar
        title="대시보드"
        subtitle="AI가 설비 정지 원인을 빠르게 찾아드립니다."
        date={formatToday()}
        action={<NewAnalysisModal />}
      />

      {loading && (
        <section className="status-card status-loading" aria-live="polite">
          <span className="spinner" /> 대시보드 데이터를 불러오는 중입니다.
        </section>
      )}
      {!loading && error && (
        <section className="status-card status-error" role="alert">
          <strong>대시보드 데이터를 불러오지 못했습니다.</strong>
          <span>{error}</span>
        </section>
      )}

      {!loading && !error && summary && (
        <>
          <section className="kpi-grid">
            {buildKpiCards(summary).map((card) => (
              <KpiCard key={card.label} {...card} />
            ))}
          </section>

          <section className="dashboard-grid">
            <div className="trend-card">
              <div className="trend-card-head">
                <h3>라인별 다운타임 추이 (최근 7일)</h3>
                <ul className="trend-legend">
                  {summary.trend.lines.map((line, index) => (
                    <li key={line.key}>
                      <span className="trend-legend-dot" style={{ background: LINE_COLORS[index % LINE_COLORS.length] }} />
                      {line.key}
                    </li>
                  ))}
                </ul>
              </div>
              {summary.trend.labels.length === 0 ? (
                <p className="helper-text">최근 7일간 다운타임 기록이 없습니다.</p>
              ) : (
                <TrendChart
                  labels={summary.trend.labels.map(formatTrendLabel)}
                  lines={summary.trend.lines.map((line, index) => ({
                    key: line.key, color: LINE_COLORS[index % LINE_COLORS.length], values: line.values,
                  }))}
                  maxY={Math.max(1, Math.ceil(Math.max(0, ...summary.trend.lines.flatMap((l) => l.values))))}
                />
              )}
            </div>

            <AiSummaryCard report={summary.latest_report} />
          </section>

          <EventsTable rows={summary.recent_events} needsReviewCount={needsReviewCount} />
        </>
      )}
    </main>
  );
}
