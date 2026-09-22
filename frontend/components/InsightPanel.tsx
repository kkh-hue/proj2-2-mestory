import { IconAlertCircle, IconCheck, IconReport } from "./icons";
import type { DowntimeReport, Severity } from "../types/report";

const SEVERITY_ORDER: Severity[] = ["중대", "보통", "경미", "판정 불가"];

// error_code가 빈 문자열인 원인도 있다(스코프 규칙: 빈 코드는 총계엔 포함, 코드별 집계에서 제외) —
// 그대로 이어붙이면 빈 배지처럼 보이니 표시용 대체 텍스트를 둔다.
function displayCode(code: string): string {
  return code.trim() === "" ? "(코드 없음)" : code;
}

// 코드 나열이 너무 길어지지 않도록 앞쪽 몇 개만 보여주고 나머지는 "외 N건"으로 묶는다.
function formatCodes(codes: string[], max = 3): string {
  const shown = codes.slice(0, max).map(displayCode).join(", ");
  return codes.length > max ? `${shown} 외 ${codes.length - max}건` : shown;
}

export default function InsightPanel({ report }: { report: DowntimeReport }) {
  const { causes, unclassified_count } = report;
  const confirmedCount = causes.filter((c) => c.is_confirmed).length;
  const unconfirmedCodes = causes.filter((c) => !c.is_confirmed).map((c) => c.error_code);
  // "확인 필요" 건수(unclassified_count)와 같은 개념이지만, 여기서는 causes 배열에서
  // 실제로 어떤 코드가 판정 불가였는지 구체적으로 보여준다 — 숫자만으론 뭘 봐야 할지 알 수 없다.
  const needsReviewCodes = causes.filter((c) => c.severity === "판정 불가").map((c) => c.error_code);

  const severityCounts = SEVERITY_ORDER
    .map((severity) => [severity, causes.filter((c) => c.severity === severity).length] as const)
    .filter(([, count]) => count > 0);

  const stats = [
    {
      icon: IconReport,
      label: "분석된 원인",
      value: `${causes.length}건`,
      note: severityCounts.length > 0
        ? severityCounts.map(([severity, count]) => `${severity} ${count}건`).join(" · ")
        : "이번 조회 조건에서 확인된 원인이 없습니다.",
    },
    {
      icon: IconCheck,
      label: "확정 원인",
      value: `${confirmedCount}건`,
      note: unconfirmedCodes.length === 0
        ? causes.length > 0 ? `${causes.length}건 모두 근거가 확인됐습니다.` : "확정할 원인이 아직 없습니다."
        : `잠정 판단: ${formatCodes(unconfirmedCodes)}`,
    },
    {
      icon: IconAlertCircle,
      label: "확인 필요",
      value: `${unclassified_count}건`,
      note: needsReviewCodes.length > 0
        ? `판정 불가 코드: ${formatCodes(needsReviewCodes)}`
        : "미등록 코드·데이터 오류 등 판정 불가 건수입니다.",
    },
  ];

  return (
    <section className="insight-panel">
      <div className="card-head">
        <h3>분석 인사이트</h3>
      </div>
      <ul className="insight-list">
        {stats.map(({ icon: Icon, label, value, note }) => (
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
        ))}
      </ul>
    </section>
  );
}
