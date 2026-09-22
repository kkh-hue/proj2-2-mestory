import CauseList from "./CauseList";
import KpiSummary from "./KpiSummary";
import PdfDownloadButton from "./PdfDownloadButton";
import TopDowntimeChart from "./TopDowntimeChart";
import type { DowntimeReport } from "../types/report";
import type { ReportStatistics } from "../types/statistics";

type Props = { report: DowntimeReport; statistics: ReportStatistics | null; statisticsError?: string | null; onNewAnalysis?: () => void };

/** 기존 ReportCard를 수정하지 않는 신규 결과 조합 컴포넌트다. */
export default function EnhancedReportResult({ report, statistics, statisticsError, onNewAnalysis }: Props) {
  return <article className="report-card">
    <div className="report-heading"><div><div className="section-kicker">ANALYSIS RESULT</div><h2>다운타임 원인 분석 리포트</h2></div><span className="report-period">{report.period}</span></div>
    <div className="condition-row"><span>라인 <b>{report.line_id}</b></span><span>설비 <b>{report.equipment_id}</b></span></div>
    <section className="cause-section"><div className="cause-title"><h3>분석된 원인</h3><span>{report.causes.length}건</span></div><CauseList causes={report.causes} /></section>
    {statistics ? <><KpiSummary data={statistics} /><TopDowntimeChart items={statistics.top_downtime_codes} codeSummaryDowntimeMin={statistics.code_summary_downtime_min} /></> : statisticsError && <p role="alert">통계를 표시하지 못했습니다: {statisticsError}</p>}
    <section className="recommendation-panel"><h3>권장 조치</h3><p>{report.recommended_action}</p></section>
    {report.unclassified_count > 0 && <section className="data-panel"><h3>데이터 확인</h3><p>확인 필요한 데이터가 {report.unclassified_count}건 있습니다.</p></section>}
    <section className="note-panel"><h3>분석 참고 사항</h3><p>{report.confidence_note}</p></section>
    <PdfDownloadButton report={report} />
    {onNewAnalysis && <div className="new-analysis-action"><button className="secondary-button" type="button" onClick={onNewAnalysis}>← 새 분석하기</button></div>}
  </article>;
}
