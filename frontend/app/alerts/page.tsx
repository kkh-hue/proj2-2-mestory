// 알림 — 디자인 목업 화면 (다른 화면과 같은 이유로 정적 값을 씀, lib/mockAlerts.ts 참고).
// 실제 알림 저장/조회 엔드포인트가 아직 없어 실제 연동은 별도 작업 필요.
import AlertBoard from "../../components/AlertBoard";
import Topbar from "../../components/Topbar";
import { IconBell, IconCalendar, IconChevronRight } from "../../components/icons";
import { alertList, alertSummary } from "../../lib/mockAlerts";

export default function AlertsPage() {
  return (
    <main className="page">
      <Topbar title="알림센터" subtitle="중요한 설비 이벤트와 분석 상태를 알려드립니다." date="2026.09.18" />

      <section className="alert-summary-row">
        <article className="alert-summary-card alert-summary-critical">
          <span className="alert-summary-icon">
            <IconBell />
          </span>
          <div>
            <span className="alert-summary-label">미확인</span>
            <div className="alert-summary-value">
              {alertSummary.unread}
              <span className="alert-summary-unit">건</span>
            </div>
          </div>
          <IconChevronRight className="alert-summary-chevron" />
        </article>
        <article className="alert-summary-card alert-summary-accent">
          <span className="alert-summary-icon">
            <IconCalendar />
          </span>
          <div>
            <span className="alert-summary-label">오늘 알림</span>
            <div className="alert-summary-value">
              {alertSummary.today}
              <span className="alert-summary-unit">건</span>
            </div>
          </div>
          <IconChevronRight className="alert-summary-chevron" />
        </article>
      </section>

      <AlertBoard items={alertList} />
    </main>
  );
}
