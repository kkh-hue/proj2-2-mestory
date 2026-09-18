"use client";

import { useState } from "react";
import AlertRow from "./AlertRow";
import type { AlertItem, AlertTone } from "../lib/mockAlerts";
import { alertTabs } from "../lib/mockAlerts";

type TabKey = (typeof alertTabs)[number]["key"];

function matchesTab(alert: AlertItem, tab: TabKey) {
  if (tab === "all") return true;
  if (tab === "unread") return alert.unread;
  if (tab === "downtime") return (["critical", "warning"] as AlertTone[]).includes(alert.tone);
  if (tab === "analysis") return alert.tone === "analysis";
  return true;
}

export default function AlertBoard({ items }: { items: AlertItem[] }) {
  const [active, setActive] = useState<TabKey>("all");
  const visible = items.filter((item) => matchesTab(item, active));

  return (
    <>
      <div className="alert-tabs">
        {alertTabs.map((tab) => (
          <button
            type="button"
            key={tab.key}
            className={`alert-tab${active === tab.key ? " active" : ""}`}
            onClick={() => setActive(tab.key)}
          >
            {tab.label} <span className="alert-tab-count">{tab.count}</span>
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
