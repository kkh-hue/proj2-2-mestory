"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { IconBell, IconChart, IconDashboard, IconEquipment, IconReport } from "./icons";
import { alertSummary } from "../lib/mockAlerts";

const NAV_ITEMS = [
  { href: "/", label: "대시보드", Icon: IconDashboard, badge: 0 },
  { href: "/downtime", label: "다운타임 분석", Icon: IconChart, badge: 0 },
  { href: "/reports", label: "리포트", Icon: IconReport, badge: 0 },
  { href: "/equipment", label: "설비 관리", Icon: IconEquipment, badge: 0 },
  { href: "/alerts", label: "알림", Icon: IconBell, badge: alertSummary.unread },
] as const;

export default function Sidebar() {
  const pathname = usePathname();

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
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
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
