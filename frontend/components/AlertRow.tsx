import Link from "next/link";
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
  const Icon = TONE_ICON[alert.tone];
  // report-* 알림은 실제 리포트 상세로, downtime-* 알림은 해당 설비 화면으로 보낸다
  // (개별 다운타임 기록 상세 화면은 아직 없다).
  const href = alert.id.startsWith("report-") ? `/reports/${alert.id.slice("report-".length)}` : "/equipment";

  return (
    <article className={`alert-row alert-tone-${alert.tone}`}>
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
        <Link href={href} className="secondary-button">
          보기
        </Link>
        <IconChevronRight className="events-row-chevron" />
      </div>
    </article>
  );
}
