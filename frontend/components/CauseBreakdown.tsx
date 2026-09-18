import { IconAlertCircle, IconLayers } from "./icons";
import type { DowntimeCause } from "../types/report";

const SEVERITY_METER: Record<DowntimeCause["severity"], { width: number; tier: "critical" | "warning" | "ok" | "unknown" }> = {
  "중대": { width: 90, tier: "critical" },
  "보통": { width: 60, tier: "warning" },
  "경미": { width: 30, tier: "ok" },
  "판정 불가": { width: 12, tier: "unknown" },
};

// 개별 사건 발생 건수·시간은 출력 계약(DowntimeReport)에 없는 값이라 지어내지 않는다 —
// 대신 실제로 있는 값(심각도)만큼만 막대 길이로 보여준다.
export default function CauseBreakdown({ causes }: { causes: DowntimeCause[] }) {
  return (
    <section className="cause-breakdown-card">
      <div className="card-head">
        <h3>원인별 분석</h3>
        <span className="card-head-note">막대 길이는 심각도 기준입니다</span>
      </div>
      {causes.length === 0 ? (
        <p className="no-causes">
          <IconAlertCircle /> 확인된 원인이 없습니다. 원본 로그와 현장 상황을 확인해 주세요.
        </p>
      ) : (
        <ul className="breakdown-list">
          {causes.map((cause, index) => {
            const meter = SEVERITY_METER[cause.severity];
            return (
              <li key={`${cause.error_code}-${index}`}>
                <span className="breakdown-icon" aria-hidden="true">
                  <IconLayers />
                </span>
                <div className="breakdown-main">
                  <div className="breakdown-top">
                    <span className="breakdown-code">{cause.error_code}</span>
                    <span className="breakdown-desc">{cause.description}</span>
                  </div>
                  <span className="breakdown-meter-track">
                    <span className={`breakdown-meter-fill meter-${meter.tier}`} style={{ width: `${meter.width}%` }} />
                  </span>
                </div>
                <span className={`severity-badge severity-badge-${meter.tier}`}>{cause.severity}</span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
