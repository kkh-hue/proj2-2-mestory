import { IconCheckCircle, IconChevronRight, IconCpu, IconSiren, IconTriangleWarning } from "./icons";
import type { AlertItem } from "../lib/mockAlerts";

const TONE_ICON = { critical: IconSiren, warning: IconTriangleWarning, analysis: IconCpu, report: IconCheckCircle };

export default function AlertRow({ alert }: { alert: AlertItem }) {
  const Icon = TONE_ICON[alert.tone];
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
        <span className="alert-date">{alert.date}</span>
        <span className={`alert-dot${alert.unread ? " alert-dot-unread" : ""}`} aria-hidden="true" />
        <button type="button" className="secondary-button">
          보기
        </button>
        <IconChevronRight className="events-row-chevron" />
      </div>
    </article>
  );
}
