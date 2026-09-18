// 대시보드 목업 데이터 — 백엔드에 집계용 엔드포인트(요약 통계/추이/이벤트 목록)가
// 아직 없어서(지금은 POST /report 단발 조회만 존재) 화면 레이아웃 확인용으로 정적 값을 씀.
// 실제 집계 API가 생기면 이 파일을 지우고 fetch로 교체할 것.

export type KpiDelta = { direction: "up" | "down"; percent: number; good: boolean };

export type KpiCardData = {
  label: string;
  value: string;
  delta: KpiDelta;
  icon: "clock" | "check" | "timer" | "gauge";
};

export const kpiCards: KpiCardData[] = [
  { label: "오늘 다운타임", value: "2h 18m", delta: { direction: "up", percent: 42, good: false }, icon: "clock" },
  { label: "분석 완료", value: "24건", delta: { direction: "up", percent: 71, good: true }, icon: "check" },
  { label: "평균 복구시간", value: "38분", delta: { direction: "down", percent: 36, good: true }, icon: "timer" },
  { label: "가동률", value: "91.4%", delta: { direction: "up", percent: 2.8, good: true }, icon: "gauge" },
];

export const trendSeries = {
  labels: ["09.12\n(토)", "09.13\n(일)", "09.14\n(월)", "09.15\n(화)", "09.16\n(수)", "09.17\n(목)", "09.18\n(금)"],
  lines: [
    { key: "LINE-A", color: "var(--chart-a)", values: [1.9, 2.4, 2.6, 4.1, 2.9, 2.4, 1.9] },
    { key: "LINE-B", color: "var(--chart-b)", values: [1.3, 1.5, 1.3, 2.1, 1.7, 1.2, 1.2] },
    { key: "LINE-C", color: "var(--chart-c)", values: [0.7, 0.8, 0.7, 1.3, 0.8, 0.7, 0.8] },
  ],
  maxY: 5,
};

export const aiSummary = {
  cause: "냉각수 압력 저하",
  confidence: 87,
  description: "냉각수 압력이 기준치 이하로 떨어져 설비가 자동 정지되었습니다.",
  breakdown: [
    { label: "냉각수 압력 저하", percent: 42 },
    { label: "전원 이상", percent: 26 },
    { label: "센서 오류", percent: 18 },
    { label: "기타", percent: 14 },
  ],
};

export type DowntimeEventRow = {
  equipmentId: string;
  equipmentName: string;
  line: string;
  occurredAt: string;
  recoveredAt: string;
  durationMin: number;
  severity: "긴급" | "주의" | "정상";
  status: "복구 완료" | "분석 중";
  cause: string;
};

export const recentEvents: DowntimeEventRow[] = [
  { equipmentId: "EQ-021", equipmentName: "프레스 라인", line: "LINE-A", occurredAt: "2026.09.18 14:32", recoveredAt: "2026.09.18 15:14", durationMin: 42, severity: "긴급", status: "복구 완료", cause: "냉각수 압력 저하" },
  { equipmentId: "EQ-114", equipmentName: "조립 로봇", line: "LINE-B", occurredAt: "2026.09.18 11:06", recoveredAt: "2026.09.18 11:48", durationMin: 42, severity: "주의", status: "복구 완료", cause: "전원 이상" },
  { equipmentId: "EQ-008", equipmentName: "비전 검사기", line: "LINE-C", occurredAt: "2026.09.18 09:21", recoveredAt: "2026.09.18 09:37", durationMin: 16, severity: "정상", status: "복구 완료", cause: "센서 오류" },
];

export const needsReviewCount = 3;
