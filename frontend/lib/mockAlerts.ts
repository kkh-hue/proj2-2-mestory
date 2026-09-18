// "알림" 화면 목업 데이터 — 다른 화면과 같은 이유로 정적 값을 씀.
// 실제 알림 저장/조회 엔드포인트가 생기면 교체 대상.

export type AlertTone = "critical" | "warning" | "analysis" | "report";

export const alertSummary = { unread: 3, today: 12 };

export const alertTabs = [
  { key: "all", label: "전체", count: 12 },
  { key: "unread", label: "미확인", count: 3 },
  { key: "downtime", label: "다운타임", count: 2 },
  { key: "analysis", label: "분석 완료", count: 5 },
] as const;

export type AlertItem = {
  id: string;
  tone: AlertTone;
  tag: string;
  title: string;
  description: string;
  date: string;
  unread: boolean;
};

export const alertList: AlertItem[] = [
  {
    id: "a1",
    tone: "critical",
    tag: "긴급",
    title: "EQ-021 프레스 라인 정지 감지",
    description: "프레스 라인이 3분 전 정지되었습니다. 원인 분석이 필요합니다.",
    date: "2026.09.18 14:32",
    unread: true,
  },
  {
    id: "a2",
    tone: "warning",
    tag: "주의",
    title: "EQ-114 조립 로봇 점검 필요",
    description: "조립 로봇에서 이상 진동이 감지되었습니다. 점검을 권장합니다.",
    date: "2026.09.18 11:06",
    unread: true,
  },
  {
    id: "a3",
    tone: "analysis",
    tag: "분석 완료",
    title: "AI 원인 분석 완료",
    description: "EQ-008 비전 검사기의 이상 패턴 분석이 완료되었습니다. 상세 리포트를 확인하세요.",
    date: "2026.09.18 09:37",
    unread: true,
  },
  {
    id: "a4",
    tone: "report",
    tag: "리포트 생성 완료",
    title: "리포트 생성 완료",
    description: "EQ-114 조립 로봇의 분석 리포트가 생성되었습니다. 리포트에서 확인하세요.",
    date: "2026.09.18 08:21",
    unread: false,
  },
  {
    id: "a5",
    tone: "analysis",
    tag: "분석 완료",
    title: "AI 원인 분석 완료",
    description: "EQ-008 비전 검사기의 이상 원인이 '카메라 오염'으로 분석되었습니다.",
    date: "2026.09.18 07:46",
    unread: false,
  },
];
