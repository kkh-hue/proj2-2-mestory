// 설비 관리 — 디자인 목업 화면 (다른 화면과 같은 이유로 정적 값을 씀, lib/mockEquipment.ts 참고).
// 설비 마스터/상태 조회용 백엔드 엔드포인트가 아직 없어 실제 연동은 별도 작업 필요.
import EquipmentBoard from "../../components/EquipmentBoard";
import Topbar from "../../components/Topbar";
import { IconCheck, IconPlus, IconReport, IconStopCircle, IconTriangleWarning } from "../../components/icons";
import { equipmentList, equipmentSummary } from "../../lib/mockEquipment";

const SUMMARY_ICON = { total: IconReport, ok: IconCheck, warn: IconTriangleWarning, stop: IconStopCircle };
const SUMMARY_TONE = { total: "tone-purple", ok: "tone-ok", warn: "tone-warn", stop: "tone-stop" };

export default function EquipmentPage() {
  return (
    <main className="page">
      <Topbar
        title="설비 관리"
        subtitle="라인과 설비 상태를 한눈에 확인하세요."
        date="2026.09.18"
        action={
          <button type="button" className="new-analysis-button">
            <IconPlus />
            설비 등록
          </button>
        }
      />

      <section className="equipment-summary-grid">
        {equipmentSummary.map((item) => {
          const Icon = SUMMARY_ICON[item.key];
          return (
            <article className="equipment-summary-card" key={item.key}>
              <span className={`equipment-summary-icon ${SUMMARY_TONE[item.key]}`}>
                <Icon />
              </span>
              <span className="equipment-summary-label">{item.label}</span>
              <div className="equipment-summary-value">{item.value}</div>
              <p className="equipment-summary-note">{item.note}</p>
            </article>
          );
        })}
      </section>

      <EquipmentBoard items={equipmentList} />
    </main>
  );
}
