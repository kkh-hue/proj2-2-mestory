"use client";

import AlertRow from "./AlertRow";
import type { AlertItem, AlertTone } from "../types/alert";

export const TAB_DEFS = [
  { key: "all", label: "전체" },
  { key: "unread", label: "미확인" },
  { key: "today", label: "오늘" },
  { key: "downtime", label: "다운타임" },
  { key: "analysis", label: "분석 완료" },
] as const;

export type TabKey = (typeof TAB_DEFS)[number]["key"];

// "오늘"은 실제 오늘이 아니라 화면에서 고른 기준일(asOf, YYYY-MM-DD)이다 —
// 다른 날짜를 골랐는데 실제 오늘과 비교하면 "오늘" 탭이 항상 비어 버린다.
function isSameDay(iso: string, asOf: string) {
  const date = new Date(iso);
  const local = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
  return local === asOf;
}

export function matchesTab(alert: AlertItem, tab: TabKey, asOf: string) {
  if (tab === "all") return true;
  if (tab === "unread") return alert.unread;
  if (tab === "today") return isSameDay(alert.date, asOf);
  if (tab === "downtime") return (["critical", "warning"] as AlertTone[]).includes(alert.tone);
  if (tab === "analysis") return alert.tone === "analysis";
  return true;
}

export default function AlertBoard({
  items,
  asOf,
  active,
  onActiveChange,
}: {
  items: AlertItem[];
  asOf: string;
  active: TabKey;
  onActiveChange: (tab: TabKey) => void;
}) {
  const visible = items.filter((item) => matchesTab(item, active, asOf));

  return (
    <>
      <div className="alert-tabs">
        {TAB_DEFS.map((tab) => (
          <button
            type="button"
            key={tab.key}
            className={`alert-tab${active === tab.key ? " active" : ""}`}
            onClick={() => onActiveChange(tab.key)}
          >
            {tab.label} <span className="alert-tab-count">{items.filter((item) => matchesTab(item, tab.key, asOf)).length}</span>
          </button>
        ))}
      </div>

      <div className="alert-list">
        {visible.length === 0 ? (
          <p className="placeholder-card">이 조건에 해당하는 알림이 없습니다.</p>
        ) : (
          visible.map((alert) => <AlertRow alert={alert} key={alert.id} />)
        )}
      </div>
    </>
  );
}
