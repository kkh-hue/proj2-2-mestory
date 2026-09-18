import Topbar from "../../components/Topbar";

export default function EquipmentPage() {
  return (
    <main className="page">
      <Topbar title="설비 관리" subtitle="라인·설비 목록과 상태를 관리합니다." />
      <section className="placeholder-card">
        <p>준비 중입니다. 설비 마스터 조회 API가 추가되면 이 화면에 라인/설비 목록이 표시됩니다.</p>
      </section>
    </main>
  );
}
