"use client";

import { useCallback, useState } from "react";
import { createReport } from "../lib/api";
import { fetchReportStatistics } from "../lib/statisticsApi";
import type { DowntimeReport, ReportRequest } from "../types/report";
import type { ReportStatistics } from "../types/statistics";

type AnalysisRequest = Omit<ReportRequest, "session_id"> & { session_id?: string | null };

/** 기존 page.tsx와 독립적인 report/statistics 병렬 요청 준비 hook이다. */
export function useReportAnalysis() {
  const [report, setReport] = useState<DowntimeReport | null>(null);
  const [statistics, setStatistics] = useState<ReportStatistics | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);
  const [statisticsError, setStatisticsError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const runAnalysis = useCallback(async (request: AnalysisRequest) => {
    setLoading(true); setReportError(null); setStatisticsError(null); setReport(null); setStatistics(null);
    const [reportResult, statisticsResult] = await Promise.allSettled([createReport(request), fetchReportStatistics(request)]);
    if (reportResult.status === "fulfilled") setReport(reportResult.value);
    else setReportError(reportResult.reason instanceof Error ? reportResult.reason.message : "분석 요청에 실패했습니다.");
    if (statisticsResult.status === "fulfilled") setStatistics(statisticsResult.value);
    else setStatisticsError(statisticsResult.reason instanceof Error ? statisticsResult.reason.message : "통계 요청에 실패했습니다.");
    setLoading(false);
  }, []);

  return { report, statistics, reportError, statisticsError, loading, runAnalysis };
}
