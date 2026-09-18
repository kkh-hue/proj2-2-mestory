// "리포트" 화면 목업 데이터 — 대시보드/다운타임 분석과 같은 이유로 정적 값을 씀.
// 실제로 생성된 리포트를 목록화하려면 백엔드에 리포트 저장·조회 엔드포인트가 필요함(현재 없음).

export type ReportListItem = {
  id: string;
  icon: "chart" | "clock" | "document";
  iconTone: "solid" | "soft";
  title: string;
  status: "complete" | "generating";
  date: string;
  line: string;
  tag: string;
  description: string;
};

export const reportList: ReportListItem[] = [
  {
    id: "r1",
    icon: "chart",
    iconTone: "solid",
    title: "설비 다운타임 원인 분석 리포트",
    status: "complete",
    date: "2026.09.18 14:32",
    line: "LINE-A",
    tag: "프레스 라인",
    description: "최근 7일간의 설비 다운타임 데이터를 분석하여 주요 원인과 개선 방안을 도출한 리포트입니다.",
  },
  {
    id: "r2",
    icon: "clock",
    iconTone: "soft",
    title: "주간 가동률 리포트",
    status: "complete",
    date: "2026.09.17 09:21",
    line: "LINE-B",
    tag: "조립 라인",
    description: "주간 설비 가동률 추이와 생산량, 불량률 현황을 분석한 리포트입니다.",
  },
  {
    id: "r3",
    icon: "document",
    iconTone: "soft",
    title: "LINE-A 월간 성과 리포트",
    status: "generating",
    date: "2026.09.15 16:08",
    line: "LINE-A",
    tag: "프레스 라인",
    description: "이번 달 LINE-A의 생산 실적, 가동률, 불량률 등 주요 지표를 종합 분석 중입니다.",
  },
];

export type SharedReportItem = {
  initial: string;
  name: string;
  title: string;
  date: string;
  tone: "lavender" | "purple" | "green" | "blue" | "peach";
};

export const sharedReports: SharedReportItem[] = [
  { initial: "김", name: "김민지", title: "주간 가동률 리포트", date: "2026.09.17 14:32", tone: "lavender" },
  { initial: "이", name: "이준호", title: "설비 다운타임 원인 분석 리포트", date: "2026.09.17 11:08", tone: "purple" },
  { initial: "박", name: "박서연", title: "LINE-A 월간 성과 리포트", date: "2026.09.16 16:24", tone: "green" },
  { initial: "최", name: "최지훈", title: "주간 가동률 리포트", date: "2026.09.15 13:17", tone: "blue" },
  { initial: "정", name: "정혜원", title: "설비 다운타임 원인 분석 리포트", date: "2026.09.14 09:53", tone: "peach" },
];
