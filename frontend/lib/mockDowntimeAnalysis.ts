// "다운타임 분석" 화면 목업 데이터 — 대시보드 홈(mockDashboard.ts)과 같은 이유로 정적 값을 씀.
// 실제 조건 입력 → POST /report 흐름은 /downtime/report 에 따로 있음 ("분석 실행" 버튼 연결).

export type CauseBreakdownItem = {
  key: "coolant" | "power" | "sensor" | "etc";
  label: string;
  percent: number;
};

export const causeBreakdown: CauseBreakdownItem[] = [
  { key: "coolant", label: "냉각수 압력 저하", percent: 42 },
  { key: "power", label: "전원 이상", percent: 26 },
  { key: "sensor", label: "센서 오류", percent: 18 },
  { key: "etc", label: "기타", percent: 14 },
];

export const insightStats = [
  { icon: "clock" as const, label: "총 다운타임", value: "18h 42m", note: "선택한 기간 동안 발생한 총 다운타임입니다." },
  { icon: "gauge" as const, label: "최대 영향 설비", value: "EQ-021", note: "가장 많은 다운타임이 발생한 설비입니다." },
  { icon: "shield" as const, label: "분석 신뢰도", value: "87%", note: "데이터 기반으로 분석된 신뢰도입니다." },
];

export type CauseDetailRow = {
  key: CauseBreakdownItem["key"];
  label: string;
  count: number;
  totalTime: string;
  percent: number;
  lastOccurred: string;
};

export const causeDetailRows: CauseDetailRow[] = [
  { key: "coolant", label: "냉각수 압력 저하", count: 18, totalTime: "7h 52m", percent: 42, lastOccurred: "2026.09.18 14:32" },
  { key: "power", label: "전원 이상", count: 11, totalTime: "4h 55m", percent: 26, lastOccurred: "2026.09.18 11:06" },
  { key: "sensor", label: "센서 오류", count: 8, totalTime: "3h 21m", percent: 18, lastOccurred: "2026.09.18 09:37" },
  { key: "etc", label: "기타", count: 6, totalTime: "2h 34m", percent: 14, lastOccurred: "2026.09.18 08:15" },
];
