// 다운타임 분석 — 디자인 목업 화면 (대시보드 홈과 같은 이유로 정적 값을 씀, lib/mockDowntimeAnalysis.ts 참고).
// "분석 실행" 버튼을 누르면 실제 POST /report를 호출하는 화면(/downtime/report)으로 이동한다.
import FilterCard from "../../components/FilterCard";
import Topbar from "../../components/Topbar";
import {
  IconBolt,
  IconCalendar,
  IconChevronDown,
  IconChevronRight,
  IconClock,
  IconDots,
  IconEquipment,
  IconGauge,
  IconChart as IconLine,
  IconAlertCircle as IconStatus,
  IconLayers,
  IconPlus,
  IconShield,
  IconSnowflake,
  IconTriangleWarning,
} from "../../components/icons";
import { causeBreakdown, causeDetailRows, insightStats } from "../../lib/mockDowntimeAnalysis";

const CAUSE_ICON = { coolant: IconSnowflake, power: IconBolt, sensor: IconTriangleWarning, etc: IconDots } as const;
const CAUSE_TONE = { coolant: "tone-purple", power: "tone-coral", sensor: "tone-amber", etc: "tone-gray" } as const;
const INSIGHT_ICON = { clock: IconClock, gauge: IconGauge, shield: IconShield } as const;

export default function DowntimeAnalysisPage() {
  return (
    <main className="page">
      <Topbar
        title="다운타임 분석"
        subtitle="설비별 다운타임 원인과 발생 현황을 분석하여 가동률 향상에 활용하세요."
        date="2026.09.18"
        action={
          <a href="/downtime/report" className="new-analysis-button">
            <IconPlus />
            분석 실행
          </a>
        }
      />

      <div className="filter-row filter-row-4">
        <FilterCard icon={<IconCalendar />} label="기간">
          <span className="filter-value-display">
            2026.09.18 ~ 2026.09.18
            <IconChevronDown className="filter-chevron" />
          </span>
        </FilterCard>
        <FilterCard icon={<IconLine />} label="라인">
          <span className="filter-value-display">
            전체 라인
            <IconChevronDown className="filter-chevron" />
          </span>
        </FilterCard>
        <FilterCard icon={<IconEquipment />} label="설비">
          <span className="filter-value-display">
            전체 설비
            <IconChevronDown className="filter-chevron" />
          </span>
        </FilterCard>
        <FilterCard icon={<IconStatus />} label="상태">
          <span className="filter-value-display">
            전체 상태
            <IconChevronDown className="filter-chevron" />
          </span>
        </FilterCard>
      </div>

      <div className="dashboard-grid">
        <section className="cause-breakdown-card">
          <div className="card-head">
            <h3>원인별 다운타임 분석</h3>
          </div>
          <ul className="breakdown-list">
            {causeBreakdown.map((item) => {
              const Icon = CAUSE_ICON[item.key];
              return (
                <li key={item.key}>
                  <span className={`breakdown-icon ${CAUSE_TONE[item.key]}`} aria-hidden="true">
                    <Icon />
                  </span>
                  <div className="breakdown-main">
                    <span className="breakdown-desc breakdown-desc-label">{item.label}</span>
                    <span className="breakdown-meter-track">
                      <span className={`breakdown-meter-fill ${CAUSE_TONE[item.key]}`} style={{ width: `${item.percent}%` }} />
                    </span>
                  </div>
                  <span className="breakdown-percent">{item.percent}%</span>
                </li>
              );
            })}
          </ul>
        </section>

        <section className="insight-panel">
          <div className="card-head">
            <h3>
              <IconLayers className="insight-title-icon" /> 분석 인사이트
            </h3>
          </div>
          <ul className="insight-list">
            {insightStats.map(({ icon, label, value, note }) => {
              const Icon = INSIGHT_ICON[icon];
              return (
                <li key={label}>
                  <span className="insight-icon">
                    <Icon />
                  </span>
                  <div>
                    <span className="insight-label">{label}</span>
                    <div className="insight-value">{value}</div>
                    <p className="insight-note">{note}</p>
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      </div>

      <section className="events-card">
        <div className="events-head">
          <h3>다운타임 원인 상세</h3>
        </div>
        <div className="events-table-wrap">
          <table className="events-table">
            <thead>
              <tr>
                <th>원인</th>
                <th>발생 건수</th>
                <th>총 시간</th>
                <th>비중</th>
                <th>최근 발생</th>
                <th aria-hidden="true" />
              </tr>
            </thead>
            <tbody>
              {causeDetailRows.map((row) => {
                const Icon = CAUSE_ICON[row.key];
                return (
                  <tr key={row.key}>
                    <td className="detail-cause-cell">
                      <span className={`breakdown-icon breakdown-icon-sm ${CAUSE_TONE[row.key]}`} aria-hidden="true">
                        <Icon />
                      </span>
                      {row.label}
                    </td>
                    <td>{row.count}건</td>
                    <td>{row.totalTime}</td>
                    <td>{row.percent}%</td>
                    <td>{row.lastOccurred}</td>
                    <td>
                      <IconChevronRight className="events-row-chevron" />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
