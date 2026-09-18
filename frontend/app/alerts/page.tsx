import Topbar from "../../components/Topbar";

export default function AlertsPage() {
  return (
    <main className="page">
      <Topbar title="알림" subtitle="확인이 필요한 이벤트를 모아봅니다." />
      <section className="placeholder-card">
        <p>준비 중입니다. 심각도가 "긴급"인 이벤트가 여기에 자동으로 모일 예정입니다.</p>
      </section>
    </main>
  );
}
