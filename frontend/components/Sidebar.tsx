"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { IconBell, IconChart, IconDashboard, IconEquipment, IconReport, IconRobot } from "./icons";
import { alertSummary } from "../lib/mockAlerts";

const NAV_ITEMS = [
  { href: "/", label: "대시보드", Icon: IconDashboard, badge: 0 },
  { href: "/downtime", label: "다운타임 분석", Icon: IconChart, badge: 0 },
  { href: "/reports", label: "리포트", Icon: IconReport, badge: 0 },
  { href: "/equipment", label: "설비 관리", Icon: IconEquipment, badge: 0 },
  { href: "/downtime/ai", label: "AI 원인분석", Icon: IconRobot, badge: 0 },
  { href: "/alerts", label: "알림", Icon: IconBell, badge: alertSummary.unread },
] as const;

export default function Sidebar() {
  const pathname = usePathname();
  // "/downtime"과 "/downtime/ai"처럼 경로가 겹칠 때, 더 길게(구체적으로) 일치하는
  // 메뉴 하나만 active로 표시한다 (안 그러면 AI 원인분석 화면에서 둘 다 켜져 보인다).
  const activeHref = NAV_ITEMS
    .filter((item) => (item.href === "/" ? pathname === "/" : pathname.startsWith(item.href)))
    .sort((a, b) => b.href.length - a.href.length)[0]?.href;

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="brand-mark">
          <Image src="/logo.png" alt="MESTORY" width={40} height={40} priority />
        </div>
        <div>
          <div className="sidebar-title">MESTORY</div>
          <div className="sidebar-subtitle">MANUFACTURING INTELLIGENCE</div>
        </div>
      </div>
      <nav>
        <ul className="sidebar-nav">
          {NAV_ITEMS.map(({ href, label, Icon, badge }) => {
            const active = href === activeHref;
            return (
              <li key={href}>
                <Link href={href} className={`sidebar-link${active ? " active" : ""}`}>
                  <Icon />
                  <span>{label}</span>
                  {badge > 0 && <span className="sidebar-badge">{badge}</span>}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </aside>
  );
}
