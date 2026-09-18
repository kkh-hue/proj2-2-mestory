import type { DowntimeCause } from "../types/report";

// Record<...> 라서 severity에 값이 하나라도 빠지면 TypeScript가 잡아 준다.
// 실제로 "판정 불가"가 빠져 있어서 그 배지가 class="severity undefined"로 렌더링되고 있었다.
const severityClass: Record<DowntimeCause["severity"], string> = { "중대": "severity-high", "보통": "severity-medium", "경미": "severity-low", "판정 불가": "severity-unknown" };

export default function CauseList({ causes }: { causes: DowntimeCause[] }) {
  if (causes.length === 0) return <p className="no-causes">확인된 원인이 없습니다. 원본 로그와 현장 상황을 확인해 주세요.</p>;
  const orderedCauses = [...causes].sort((a, b) => Number(b.is_confirmed) - Number(a.is_confirmed));
  return <div className="cause-list">{orderedCauses.map((cause, index) => <article className="cause-item" key={`${cause.error_code}-${index}`}>
    <div className="cause-top"><span className="cause-code">{cause.error_code}</span><span className={`severity ${severityClass[cause.severity]}`}>{cause.severity}</span><span className="confirmation">{cause.is_confirmed ? "확정" : "확인 필요"}</span></div>
    <h4>{cause.description}</h4>
    <details><summary>판단 근거 보기</summary><p>{cause.evidence}</p></details>
  </article>)}</div>;
}
