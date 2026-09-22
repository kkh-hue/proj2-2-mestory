"use client";

import { useCallback, useState } from "react";
import { getAnalysisHistory, listAnalysisHistory, saveReportHistory } from "../lib/historyApi";
import type { AnalysisHistoryEntry, HistoryApiItem } from "../types/authHistory";
import type { DowntimeReport, ReportRequest } from "../types/report";

function toEntry(item: HistoryApiItem, userId: string): AnalysisHistoryEntry {
  return { analysis_id: item.history_id, user_id: userId, created_at: item.analyzed_at, period: item.report_json.period, line_id: item.line_id ?? item.report_json.line_id, equipment_id: item.equipment_id ?? item.report_json.equipment_id, report: item.report_json };
}

export function useAnalysisHistory(token: string | null, userId: string | null) {
  const [entries, setEntries] = useState<AnalysisHistoryEntry[]>([]);
  const [selectedReport, setSelectedReport] = useState<DowntimeReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const load = useCallback(async () => { if (!token || !userId) return; setIsLoading(true); setError(null); try { setEntries((await listAnalysisHistory(token)).map((item) => toEntry(item, userId))); } catch (cause) { setError(cause instanceof Error ? cause.message : "분석 기록을 불러오지 못했습니다."); } finally { setIsLoading(false); } }, [token, userId]);
  const save = useCallback(async (request: ReportRequest, report: DowntimeReport) => { if (!token || !userId) return null; const saved = await saveReportHistory(token, request, report); if (!saved) return null; const entry = toEntry(saved, userId); setEntries((current) => [entry, ...current]); return entry; }, [token, userId]);
  const select = useCallback(async (historyId: string) => { if (!token || !userId) return null; const item = await getAnalysisHistory(token, historyId); const entry = toEntry(item, userId); setSelectedReport(entry.report); return entry.report; }, [token, userId]);
  return { entries, selectedReport, error, isLoading, load, save, select, setSelectedReport };
}
