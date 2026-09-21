import { IconArrowDown, IconArrowUp, IconCheck, IconClock, IconGauge, IconTimer } from "./icons";
import type { KpiDelta } from "../types/dashboard";

const ICONS = { clock: IconClock, check: IconCheck, timer: IconTimer, gauge: IconGauge };

export type KpiCardData = {
  label: string;
  value: string;
  delta: KpiDelta & { good: boolean };
  icon: "clock" | "check" | "timer" | "gauge";
};

export default function KpiCard({ label, value, delta, icon }: KpiCardData) {
  const Icon = ICONS[icon];
  const DeltaIcon = delta.direction === "up" ? IconArrowUp : IconArrowDown;

  return (
    <article className="kpi-card">
      <div className={`kpi-icon kpi-icon-${icon}`}>
        <Icon />
      </div>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      <div className={`kpi-delta ${delta.good ? "kpi-delta-good" : "kpi-delta-bad"}`}>
        <DeltaIcon />
        {delta.percent}% <span className="kpi-delta-note">(전일 대비)</span>
      </div>
    </article>
  );
}
