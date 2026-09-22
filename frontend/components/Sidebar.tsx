"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { IconBell, IconChart, IconDashboard, IconEquipment, IconReport, IconRobot } from "./icons";
import { listAlerts } from "../lib/api";
import { useAuth } from "./AuthProvider";

const NAV_ITEMS = [
  { href: "/", label: "대시보드", Icon: IconDashboard },
  { href: "/downtime", label: "다운타임 분석", Icon: IconChart },
  { href: "/reports", label: "리포트", Icon: IconReport },
  { href: "/equipment", label: "설비 현황", Icon: IconEquipment },
  { href: "/downtime/ai", label: "AI 원인분석", Icon: IconRobot },
  { href: "/alerts", label: "알림", Icon: IconBell },
] as const;

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [unreadAlerts, setUnreadAlerts] = useState(0);
  const [alertsError, setAlertsError] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const { user, logout } = useAuth();

  useEffect(() => {
    listAlerts()
      .then((alerts) => {
        setUnreadAlerts(alerts.filter((a) => a.unread).length);
        setAlertsError(false);
      })
      .catch(() => setAlertsError(true));
  }, []);

  const displayName = user?.email.split("@", 1)[0] || "사용자";
  function handleLogout() {
    logout();
    setAccountOpen(false);
    router.push("/login");
  }

  // "/downtime"과 "/downtime/ai"처럼 경로가 겹칠 때, 더 길게(구체적으로) 일치하는
  // 메뉴 하나만 active로 표시한다 (안 그러면 AI 원인분석 화면에서 둘 다 켜져 보인다).
  const activeHref = NAV_ITEMS
    .filter((item) => (item.href === "/" ? pathname === "/" : pathname.startsWith(item.href)))
    .sort((a, b) => b.href.length - a.href.length)[0]?.href;

  return (
    <aside className="sidebar" style={{ display: "flex", flexDirection: "column" }}>
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
                  {href === "/alerts" && alertsError ? (
                    <span className="sidebar-badge" role="status" aria-label="알림을 불러오지 못했습니다" title="알림을 불러오지 못했습니다">!</span>
                  ) : badge > 0 ? (
                    <span className="sidebar-badge">{badge}</span>
                  ) : null}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
      <div style={{ position: "relative", marginTop: "auto", padding: "18px 8px 0" }}>
        {user && accountOpen && (
          <div
            role="menu"
            style={{
              position: "absolute",
              right: 8,
              bottom: "calc(100% + 8px)",
              width: "min(240px, calc(100vw - 32px))",
              padding: 12,
              border: "1px solid var(--line)",
              borderRadius: 14,
              background: "#fff",
              boxShadow: "0 12px 28px rgba(45,58,90,.14)",
              zIndex: 10,
            }}
          >
            <div style={{ padding: "3px 6px 10px", borderBottom: "1px solid var(--line)" }}>
              <strong style={{ display: "block", color: "var(--ink)", fontSize: 13 }}>{displayName}</strong>
              <span style={{ display: "block", marginTop: 7, color: "#5b667c", fontSize: 11, overflowWrap: "anywhere" }}>{user.email}</span>
            </div>
            <button type="button" onClick={() => router.push("/downtime/ai")} style={accountMenuButtonStyle}>내 대화 보기</button>
            <button type="button" onClick={() => setAccountOpen(false)} style={accountMenuButtonStyle}>사용자 정보</button>
            <button type="button" onClick={handleLogout} style={{ ...accountMenuButtonStyle, color: "var(--danger)" }}>로그아웃</button>
          </div>
        )}
        {user ? (
          <button
            type="button"
            aria-expanded={accountOpen}
            aria-label="계정 메뉴"
            onClick={() => setAccountOpen((open) => !open)}
            style={{ ...accountButtonStyle, width: "100%" }}
          >
            <span style={{ minWidth: 0, textAlign: "left" }}>
              <strong style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "var(--ink)", fontSize: 13 }}>{displayName}</strong>
            </span>
            <span aria-hidden="true" style={{ color: "var(--muted)", fontSize: 13 }}>{accountOpen ? "⌃" : "⌄"}</span>
          </button>
        ) : (
          <button type="button" onClick={() => router.push("/login")} style={{ ...accountButtonStyle, width: "100%", justifyContent: "center", color: "var(--accent)" }}>
            로그인
          </button>
        )}
      </div>
    </aside>
  );
}

const accountButtonStyle = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: 10,
  border: "1px solid var(--line)",
  borderRadius: 11,
  padding: "9px 10px",
  background: "#fff",
  cursor: "pointer",
  fontFamily: "inherit",
};

const accountMenuButtonStyle = {
  display: "block",
  width: "100%",
  border: 0,
  borderRadius: 8,
  padding: "9px 6px",
  background: "transparent",
  color: "#4a5468",
  textAlign: "left" as const,
  fontFamily: "inherit",
  fontSize: 12,
  cursor: "pointer",
};
