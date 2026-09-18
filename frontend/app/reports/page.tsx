import Topbar from "../../components/Topbar";

export default function ReportsPage() {
  return (
    <main className="page">
      <Topbar title="리포트" subtitle="지난 분석 리포트를 모아봅니다." />
      <section className="placeholder-card">
        <p>준비 중입니다. 지금은 "다운타임 분석" 탭에서 생성한 리포트를 그 화면에서 바로 확인할 수 있습니다.</p>
      </section>
    </main>
  );
}
