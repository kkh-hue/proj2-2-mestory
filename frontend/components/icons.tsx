// 대시보드 전용 미니 아이콘 세트 — 외부 아이콘 라이브러리 의존성 없이 인라인 SVG로 유지
import type { SVGProps } from "react";

function base(props: SVGProps<SVGSVGElement>) {
  return { width: 20, height: 20, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, ...props };
}

export function IconDashboard(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><rect x="3.5" y="3.5" width="7" height="7" rx="1.5" /><rect x="13.5" y="3.5" width="7" height="7" rx="1.5" /><rect x="3.5" y="13.5" width="7" height="7" rx="1.5" /><rect x="13.5" y="13.5" width="7" height="7" rx="1.5" /></svg>;
}

export function IconChart(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><path d="M4 19V5" /><path d="M4 19h16" /><path d="M8 15l3-4 3 2.5L18 8" /></svg>;
}

export function IconReport(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><path d="M7 3.5h7l4 4V20a.7.7 0 0 1-.7.7H7A.7.7 0 0 1 6.3 20V4.2A.7.7 0 0 1 7 3.5Z" /><path d="M14 3.5V8h4.3" /><path d="M9 12.5h6M9 16h6" /></svg>;
}

export function IconEquipment(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><path d="M10.4 3.6h3.2l.5 2.3a6.4 6.4 0 0 1 1.9 1.1l2.2-.8 1.6 2.8-1.8 1.5a6.5 6.5 0 0 1 0 2.2l1.8 1.5-1.6 2.8-2.2-.8a6.4 6.4 0 0 1-1.9 1.1l-.5 2.3h-3.2l-.5-2.3a6.4 6.4 0 0 1-1.9-1.1l-2.2.8-1.6-2.8 1.8-1.5a6.5 6.5 0 0 1 0-2.2L4.2 8.9l1.6-2.8 2.2.8a6.4 6.4 0 0 1 1.9-1.1z" /><circle cx="12" cy="12" r="2.6" /></svg>;
}

export function IconBell(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><path d="M6 10.5a6 6 0 0 1 12 0c0 4 1.4 5.2 1.4 5.2H4.6S6 14.5 6 10.5Z" /><path d="M10.2 18.5a1.8 1.8 0 0 0 3.6 0" /></svg>;
}

export function IconClock(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><circle cx="12" cy="12" r="8.2" /><path d="M12 7.5V12l3 2" /></svg>;
}

export function IconCheck(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><circle cx="12" cy="12" r="8.2" /><path d="M8.3 12.3l2.4 2.4 5-5.2" /></svg>;
}

export function IconTimer(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><path d="M9.5 3.5h5" /><circle cx="12" cy="13" r="7.5" /><path d="M12 9v4l2.6 1.6" /><path d="M18.2 6.2l1.3 1.3" /></svg>;
}

export function IconGauge(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><path d="M4 15.5a8 8 0 1 1 16 0" /><path d="M12 15.5 15.4 10" /><circle cx="12" cy="15.5" r="1.4" /></svg>;
}

export function IconArrowUp(props: SVGProps<SVGSVGElement>) {
  return <svg {...base({ strokeWidth: 2.2, ...props })}><path d="M12 18.5V6M6.5 11.5 12 6l5.5 5.5" /></svg>;
}

export function IconArrowDown(props: SVGProps<SVGSVGElement>) {
  return <svg {...base({ strokeWidth: 2.2, ...props })}><path d="M12 5.5V18M6.5 12.5 12 18l5.5-5.5" /></svg>;
}

export function IconChevronRight(props: SVGProps<SVGSVGElement>) {
  return <svg {...base({ strokeWidth: 2.2, ...props })}><path d="M9 5.5 15.5 12 9 18.5" /></svg>;
}

export function IconCalendar(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><rect x="3.7" y="5" width="16.6" height="15" rx="2" /><path d="M3.7 9.5h16.6" /><path d="M8 3v4M16 3v4" /></svg>;
}

export function IconPlus(props: SVGProps<SVGSVGElement>) {
  return <svg {...base({ strokeWidth: 2.4, ...props })}><path d="M12 5.5v13M5.5 12h13" /></svg>;
}

export function IconSnowflake(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><path d="M12 3.5v17M6 6l12 12M18 6 6 18" /><path d="m9 4.5 3 2.2 3-2.2M9 19.5l3-2.2 3 2.2M4.5 9l2.2 3-2.2 3M19.5 9l-2.2 3 2.2 3" /></svg>;
}

export function IconBolt(props: SVGProps<SVGSVGElement>) {
  return <svg {...base({ strokeLinejoin: "round" as const, ...props })}><path d="M13 3 5 13.5h5.5L11 21l8-11h-5.5L13 3Z" /></svg>;
}

export function IconTriangleWarning(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><path d="M12 4 21 19.5H3L12 4Z" /><path d="M12 10v4" /><circle cx="12" cy="16.7" r="0.9" fill="currentColor" stroke="none" /></svg>;
}

export function IconDots(props: SVGProps<SVGSVGElement>) {
  return <svg {...base({ strokeLinecap: "round" as const, ...props })}><circle cx="6.5" cy="12" r="1.1" fill="currentColor" stroke="none" /><circle cx="12" cy="12" r="1.1" fill="currentColor" stroke="none" /><circle cx="17.5" cy="12" r="1.1" fill="currentColor" stroke="none" /></svg>;
}

export function IconShield(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><path d="M12 3.5 19 6.3V11c0 5-3 8.1-7 9.5-4-1.4-7-4.5-7-9.5V6.3L12 3.5Z" /><path d="m8.7 12 2.3 2.3L15.3 10" /></svg>;
}

export function IconChevronDown(props: SVGProps<SVGSVGElement>) {
  return <svg {...base({ strokeWidth: 2.2, ...props })}><path d="M5.5 9 12 15.5 18.5 9" /></svg>;
}

export function IconAlertCircle(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><circle cx="12" cy="12" r="8.2" /><path d="M12 8v4.5" /><circle cx="12" cy="15.6" r="0.9" fill="currentColor" stroke="none" /></svg>;
}

export function IconLayers(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><path d="M12 3.5 20.5 8 12 12.5 3.5 8Z" /><path d="M3.5 12 12 16.5 20.5 12" /><path d="M3.5 16 12 20.5 20.5 16" /></svg>;
}

export function IconSparkle(props: SVGProps<SVGSVGElement>) {
  return <svg {...base({ strokeWidth: 1.6, ...props })}><path d="M12 3.5l1.4 4.2 4.2 1.4-4.2 1.4L12 14.7l-1.4-4.2-4.2-1.4 4.2-1.4L12 3.5Z" /><path d="M18.5 15.5l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7.7-2Z" /></svg>;
}

// 알림센터(AlertRow) 전용
export function IconCheckCircle(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><circle cx="12" cy="12" r="8.2" /><path d="M8.3 12.3l2.4 2.4 5-5.2" /></svg>;
}

export function IconCpu(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><rect x="6.5" y="6.5" width="11" height="11" rx="1.5" /><rect x="9.5" y="9.5" width="5" height="5" rx="0.8" /><path d="M9 3.5v3M15 3.5v3M9 17.5v3M15 17.5v3M3.5 9h3M3.5 15h3M17.5 9h3M17.5 15h3" /></svg>;
}

export function IconSiren(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><path d="M5 15.5a7 7 0 0 1 14 0v1.5H5Z" /><path d="M4 20h16" /><path d="M12 4v2.5M7 6l1.3 1.8M17 6l-1.3 1.8" /></svg>;
}

// 설비관리(EquipmentCard) 전용
export function IconConveyor(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><rect x="3.5" y="7.5" width="17" height="4" rx="1" /><circle cx="7.5" cy="17" r="2" /><circle cx="16.5" cy="17" r="2" /></svg>;
}

export function IconEye(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" /><circle cx="12" cy="12" r="2.6" /></svg>;
}

export function IconFan(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><circle cx="12" cy="12" r="1.8" /><path d="M12 10.2c-2.8-3-6-2.6-6-.4s3.2 2.6 6 .4" /><path d="M13.8 12c3-2.8 2.6-6 .4-6s-2.6 3.2-.4 6" /><path d="M12 13.8c2.8 3 6 2.6 6 .4s-3.2-2.6-6-.4" /></svg>;
}

export function IconPanel(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><rect x="3.5" y="4.5" width="17" height="15" rx="1.5" /><path d="M3.5 9.5h17M9 9.5V19.5" /><circle cx="6" cy="7" r="0.6" fill="currentColor" stroke="none" /><circle cx="8" cy="7" r="0.6" fill="currentColor" stroke="none" /></svg>;
}

export function IconPump(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><circle cx="10" cy="14" r="4.5" /><path d="M10 9.5V4h6M16 4v4" /><path d="M13.2 16.8 17 20.5" /></svg>;
}

export function IconRobotArm(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><path d="M4 20h4" /><path d="M6 20V13.5h5" /><circle cx="6" cy="20" r="1.3" /><circle cx="11" cy="13.5" r="1.3" /><path d="M11 13.5 16 8" /><circle cx="16" cy="8" r="1.3" /><path d="M16 8h4v4" /></svg>;
}

export function IconStamp(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><path d="M9 3.5h6l1 5h-8Z" /><rect x="9" y="8.5" width="6" height="4" /><path d="M4.5 20v-3a2 2 0 0 1 2-2h11a2 2 0 0 1 2 2v3Z" /><path d="M4.5 20h15" /></svg>;
}

export function IconStopCircle(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><circle cx="12" cy="12" r="8.2" /><rect x="9" y="9" width="6" height="6" rx="1" /></svg>;
}

// 리포트(reports/page.tsx, ReportListCard) 전용
export function IconSearch(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><circle cx="10.8" cy="10.8" r="6.3" /><path d="M15.5 15.5 20 20" /></svg>;
}

export function IconDownload(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><path d="M12 3.5v11.5M8 11l4 4 4-4" /><path d="M4.5 18.5v1a1 1 0 0 0 1 1h13a1 1 0 0 0 1-1v-1" /></svg>;
}

export function IconMoreHorizontal(props: SVGProps<SVGSVGElement>) {
  return <svg {...base({ strokeLinecap: "round" as const, ...props })}><circle cx="6.5" cy="12" r="1.1" fill="currentColor" stroke="none" /><circle cx="12" cy="12" r="1.1" fill="currentColor" stroke="none" /><circle cx="17.5" cy="12" r="1.1" fill="currentColor" stroke="none" /></svg>;
}

// AI 원인분석 대화형 화면(downtime/ai) 전용
export function IconHourglass(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><path d="M6 3.5h12M6 20.5h12" /><path d="M7 3.5v3.2c0 2 1.8 3.4 3.6 4.3.3.15.3.55 0 .7C8.8 12.8 7 14.2 7 16.3v4.2" /><path d="M17 3.5v3.2c0 2-1.8 3.4-3.6 4.3-.3.15-.3.55 0 .7 1.8.9 3.6 2.3 3.6 4.3v4.2" /></svg>;
}

export function IconLightbulb(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><path d="M9 18.5h6" /><path d="M9.5 21h5" /><path d="M12 3.5a6 6 0 0 0-3.4 10.9c.5.35.9.9.9 1.6h5a2 2 0 0 1 .9-1.6A6 6 0 0 0 12 3.5Z" /></svg>;
}

export function IconRobot(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><rect x="5" y="8.5" width="14" height="10" rx="2.5" /><path d="M12 8.5V5.5" /><circle cx="12" cy="4" r="1" fill="currentColor" stroke="none" /><circle cx="9" cy="13.5" r="1" fill="currentColor" stroke="none" /><circle cx="15" cy="13.5" r="1" fill="currentColor" stroke="none" /><path d="M9 17h6" /><path d="M3.5 11.5v3M20.5 11.5v3" /></svg>;
}

export function IconSend(props: SVGProps<SVGSVGElement>) {
  return <svg {...base({ strokeLinejoin: "round" as const, ...props })}><path d="M20.5 3.5 10.8 13.2" /><path d="M20.5 3.5 14 20.5l-3.2-7.3-7.3-3.2Z" /></svg>;
}

// 클립 아이콘 — AI 원인 분석 채팅의 이미지 첨부 버튼에 쓴다 (docs/specs/multimodal-frontend.md).
export function IconPaperclip(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><path d="M21.4 11.05 12.2 20.24a6 6 0 0 1-8.49-8.49l9.2-9.19a4 4 0 0 1 5.65 5.66l-9.19 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" /></svg>;
}

export function IconUser(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><circle cx="12" cy="8.3" r="3.3" /><path d="M5 20v-1c0-3 3-5.5 7-5.5s7 2.5 7 5.5v1" /></svg>;
}

// AI 원인분석/새 분석 요청 모달 공통
export function IconTarget(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><circle cx="12" cy="12" r="8.2" /><circle cx="12" cy="12" r="4.6" /><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" /></svg>;
}

// 새 다운타임 분석 요청 모달(NewAnalysisModal) 전용
export function IconFolder(props: SVGProps<SVGSVGElement>) {
  return <svg {...base(props)}><path d="M3.5 6.5A1 1 0 0 1 4.5 5.5h4.6l1.6 2h9.3a1 1 0 0 1 1 1V18a1 1 0 0 1-1 1H4.5a1 1 0 0 1-1-1Z" /></svg>;
}

export function IconX(props: SVGProps<SVGSVGElement>) {
  return <svg {...base({ strokeWidth: 2.2, ...props })}><path d="M6 6l12 12M18 6 6 18" /></svg>;
}
