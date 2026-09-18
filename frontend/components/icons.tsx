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

export function IconSparkle(props: SVGProps<SVGSVGElement>) {
  return <svg {...base({ strokeWidth: 1.6, ...props })}><path d="M12 3.5l1.4 4.2 4.2 1.4-4.2 1.4L12 14.7l-1.4-4.2-4.2-1.4 4.2-1.4L12 3.5Z" /><path d="M18.5 15.5l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7.7-2Z" /></svg>;
}
