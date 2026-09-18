import type { DowntimeReport } from "../types/report";
import ReportCard from "./ReportCard";

type Props = { loading: boolean; error: string; result: DowntimeReport | null; onNewAnalysis: () => void; onRetry: () => void };

export default function ChatWindow({ loading, error, result, onNewAnalysis, onRetry }: Props) {
  if (loading) return <section className="status-card status-loading" aria-live="polite"><span className="spinner" /> 분석 중입니다. 로그와 근거 데이터를 확인하고 있습니다.</section>;
  if (error) return <section className="status-card status-error" role="alert"><strong>분석을 완료하지 못했습니다.</strong><span>{error}</span><div className="status-actions"><button className="secondary-button" type="button" onClick={onNewAnalysis}>새 분석 시작</button><button className="primary-button" type="button" onClick={onRetry}>다시 시도</button></div></section>;
  if (!result) return <section className="status-card status-empty"><strong>아직 분석 결과가 없습니다.</strong><span>조건을 입력하고 분석을 시작하면 결과가 여기에 표시됩니다.</span></section>;
  return <ReportCard report={result} onNewAnalysis={onNewAnalysis} />;
}
