import type { AnalysisHistoryEntry } from "../types/authHistory";
import type { DowntimeReport } from "../types/report";

type Props = { entries: readonly AnalysisHistoryEntry[]; onSelect?: (report: DowntimeReport, entry: AnalysisHistoryEntry) => void };

/** 저장소와 연결하지 않은 사용자별 분석 이력 표시 컴포넌트다. */
export default function AnalysisHistory({ entries, onSelect }: Props) {
  if (entries.length === 0) return <section aria-labelledby="history-title"><h2 id="history-title">분석 히스토리</h2><p>저장된 분석 이력이 없습니다.</p></section>;

  return <section aria-labelledby="history-title">
    <h2 id="history-title">분석 히스토리</h2>
    <ul>
      {entries.map((entry) => <li key={entry.analysis_id}>
        <button type="button" onClick={() => onSelect?.(entry.report, entry)}>
          <time dateTime={entry.created_at}>{entry.created_at}</time> · {entry.period} · 라인 {entry.line_id} · 설비 {entry.equipment_id}
        </button>
      </li>)}
    </ul>
  </section>;
}
