"use client";

import { useRouter } from "next/navigation";
import { IconChevronRight, IconCpu, IconSiren, IconTriangleWarning } from "./icons";
import type { AlertItem } from "../types/alert";

const TONE_ICON = { critical: IconSiren, warning: IconTriangleWarning, analysis: IconCpu };

function formatDate(iso: string) {
  const date = new Date(iso);
  return `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, "0")}.${String(date.getDate()).padStart(2, "0")} ${String(
    date.getHours(),
  ).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

export default function AlertRow({ alert }: { alert: AlertItem }) {
  const router = useRouter();
  const Icon = TONE_ICON[alert.tone];
  // "분석 완료" 알림은 그 리포트 상세로, 정지 감지 알림은 그 라인·설비로 걸러진
  // 다운타임 분석 화면으로 보낸다 (개별 다운타임 기록 상세 화면은 아직 없다).
  const params = new URLSearchParams();
  if (alert.line_id) params.set("line_id", alert.line_id);
  if (alert.equipment_id) params.set("equipment_id", alert.equipment_id);
  const query = params.toString();
  const analysisHref = query ? `/downtime?${query}` : "/downtime";
  const href = alert.id.startsWith("report-") ? `/reports/${alert.id.slice("report-".length)}` : analysisHref;

  return (
    <article
      className={`alert-row alert-tone-${alert.tone} events-row-clickable`}
      role="button"
      tabIndex={0}
      onClick={() => router.push(href)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          router.push(href);
        }
      }}
    >
      <span className="alert-icon">
        <Icon />
      </span>
      <div className="alert-body">
        <div className="alert-top">
          <span className="alert-tag">{alert.tag}</span>
          <h4>{alert.title}</h4>
        </div>
        <p className="alert-desc">{alert.description}</p>
      </div>
      <div className="alert-right">
        <span className="alert-date">{formatDate(alert.date)}</span>
        <span className={`alert-dot${alert.unread ? " alert-dot-unread" : ""}`} aria-hidden="true" />
        <IconChevronRight className="events-row-chevron" />
      </div>
    </article>
  );
}
