// 알림센터 (F-07) — backend GET /alerts를 그대로 불러온다.
// 전용 알림 테이블이 없어서 downtime_log·reports에서 파생시킨 값이다 (backend/db.py 참고).
"use client";

import { useEffect, useState } from "react";
import AlertBoard, { matchesTab, type TabKey } from "../../components/AlertBoard";
import Topbar from "../../components/Topbar";
import { IconBell, IconCalendar, IconChevronRight } from "../../components/icons";
import { listAlerts } from "../../lib/api";
import type { AlertItem } from "../../types/alert";

function todayISO() {
  const date = new Date();
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [asOf, setAsOf] = useState(todayISO());
  const [activeTab, setActiveTab] = useState<TabKey>("all");

  useEffect(() => {
    setLoading(true);
    listAlerts(asOf)
      .then(setAlerts)
      .catch((cause) => setError(cause instanceof Error ? cause.message : "알림을 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, [asOf]);

  const unreadCount = alerts.filter((a) => matchesTab(a, "unread")).length;
  const todayCount = alerts.filter((a) => matchesTab(a, "today")).length;

  return (
    <main className="page">
      <Topbar
        title="알림센터"
        subtitle="중요한 설비 이벤트와 분석 상태를 알려드립니다."
        date={asOf}
        onDateChange={setAsOf}
      />

      {loading && (
        <section className="status-card status-loading" aria-live="polite">
          <span className="spinner" /> 알림을 불러오는 중입니다.
        </section>
      )}
      {!loading && error && (
        <section className="status-card status-error" role="alert">
          <strong>알림을 불러오지 못했습니다.</strong>
          <span>{error}</span>
        </section>
      )}

      {!loading && !error && (
        <>
          <section className="alert-summary-row">
            <button
              type="button"
              className="alert-summary-card alert-summary-critical events-row-clickable"
              onClick={() => setActiveTab("unread")}
            >
              <span className="alert-summary-icon">
                <IconBell />
              </span>
              <div>
                <span className="alert-summary-label">미확인</span>
                <div className="alert-summary-value">
                  {unreadCount}
                  <span className="alert-summary-unit">건</span>
                </div>
              </div>
              <IconChevronRight className="alert-summary-chevron" />
            </button>
            <button
              type="button"
              className="alert-summary-card alert-summary-accent events-row-clickable"
              onClick={() => setActiveTab("today")}
            >
              <span className="alert-summary-icon">
                <IconCalendar />
              </span>
              <div>
                <span className="alert-summary-label">오늘 알림</span>
                <div className="alert-summary-value">
                  {todayCount}
                  <span className="alert-summary-unit">건</span>
                </div>
              </div>
              <IconChevronRight className="alert-summary-chevron" />
            </button>
          </section>

          <AlertBoard items={alerts} active={activeTab} onActiveChange={setActiveTab} />
        </>
      )}
    </main>
  );
}
