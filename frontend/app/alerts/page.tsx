// 알림센터 (F-07) — backend GET /alerts를 그대로 불러온다.
// 전용 알림 테이블이 없어서 downtime_log·reports에서 파생시킨 값이다 (backend/db.py 참고).
"use client";

import { useEffect, useState } from "react";
import AlertBoard, { type TabKey } from "../../components/AlertBoard";
import Topbar from "../../components/Topbar";
import { listAlerts } from "../../lib/api";
import { todayKst } from "../../lib/date";
import type { AlertItem } from "../../types/alert";

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [asOf, setAsOf] = useState(todayKst());
  const [activeTab, setActiveTab] = useState<TabKey>("all");

  useEffect(() => {
    let cancelled = false; // 날짜를 빠르게 바꿀 때 늦게 도착한 이전 응답이 덮어쓰지 않게
    setLoading(true);
    setError(""); // 한 번 실패한 뒤 다른 날짜를 골라도 오류 화면에 갇히지 않게
    listAlerts(asOf)
      .then((data) => !cancelled && setAlerts(data))
      .catch((cause) => !cancelled && setError(cause instanceof Error ? cause.message : "알림을 불러오지 못했습니다."))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [asOf]);

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
        <AlertBoard items={alerts} asOf={asOf} active={activeTab} onActiveChange={setActiveTab} />
      )}
    </main>
  );
}
