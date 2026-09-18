"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { IconBell, IconChart, IconDashboard, IconEquipment, IconReport, IconRobot } from "./icons";
import { listAlerts } from "../lib/api";

const NAV_ITEMS = [
  { href: "/", label: "대시보드", Icon: IconDashboard },
  { href: "/downtime", label: "다운타임 분석", Icon: IconChart },
  { href: "/reports", label: "리포트", Icon: IconReport },
  { href: "/equipment", label: "설비 관리", Icon: IconEquipment },
  { href: "/downtime/ai", label: "AI 원인분석", Icon: IconRobot },
  { href: "/alerts", label: "알림", Icon: IconBell },
] as const;

export default function Sidebar() {
  const pathname = usePathname();
  const [unreadAlerts, setUnreadAlerts] = useState(0);

  useEffect(() => {
    listAlerts()
      .then((alerts) => setUnreadAlerts(alerts.filter((a) => a.unread).length))
      .catch(() => setUnreadAlerts(0));
  }, []);

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
          {NAV_ITEMS.map(({ href, label, Icon }) => {
            const active = href === activeHref;
            const badge = href === "/alerts" ? unreadAlerts : 0;
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
