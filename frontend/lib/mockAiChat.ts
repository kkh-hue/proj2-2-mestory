// "AI 원인 분석" 대화형 화면 목업 데이터 — 다른 화면과 같은 이유로 정적 값을 씀.
// 실제로는 이 대화가 backend POST /report(에이전트) 호출로 이어져야 하며, 지금은 화면 레이아웃 확인용.
import { aiSummary } from "./mockDashboard";

export const userQuestion = {
  text: "EQ-021 프레스 라인의 다운타임 원인을 요약해줘",
  time: "09.18 15:24",
};

export const aiAnswer = {
  causeHighlight: aiSummary.cause,
  detailRows: [
    { icon: "clock" as const, label: "발생 시점", value: "2026.09.18 14:32" },
    { icon: "warning" as const, label: "추정 원인", value: "냉각수 펌프 압력 18% 하락" },
    { icon: "hourglass" as const, label: "영향 시간", value: "42분" },
    { icon: "shield" as const, label: "분석 신뢰도", value: `${aiSummary.confidence}%` },
  ],
  time: "09.18 15:24",
};

export const recommendedActions = ["냉각수 펌프 필터 점검", "압력 센서 교정", "최근 7일 동일 패턴 확인"];

export const relatedEquipment = { id: "EQ-021", name: "프레스 라인", severity: "긴급" as const };
