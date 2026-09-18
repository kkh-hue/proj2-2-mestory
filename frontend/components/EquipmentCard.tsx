import { IconChevronRight, IconCheck, IconConveyor, IconEye, IconFan, IconPanel, IconPump, IconRobotArm, IconStamp, IconStopCircle, IconTriangleWarning } from "./icons";
import type { EquipmentItem } from "../lib/mockEquipment";

const ICON = { stamp: IconStamp, robotArm: IconRobotArm, eye: IconEye, conveyor: IconConveyor, pump: IconPump, fan: IconFan, panel: IconPanel };

const STATUS_TONE = {
  정상: { className: "status-tone-ok", Icon: IconCheck },
  주의: { className: "status-tone-warn", Icon: IconTriangleWarning },
  정지: { className: "status-tone-stop", Icon: IconStopCircle },
} as const;

export default function EquipmentCard({ item }: { item: EquipmentItem }) {
  const Icon = ICON[item.icon];
  const { className, Icon: StatusIcon } = STATUS_TONE[item.status];

  return (
    <article className={`equipment-card ${className}`}>
      <div className="equipment-card-top">
        <span className="equipment-icon">
          <Icon />
        </span>
        <span className="equipment-id">{item.id}</span>
        <span className="status-badge-pill">
          <StatusIcon /> {item.status}
        </span>
        <IconChevronRight className="events-row-chevron" />
      </div>
      <h4 className="equipment-name">{item.name}</h4>
      <span className="equipment-line">
        <span className="equipment-line-dot" /> {item.line}
      </span>
      <div className="equipment-stats">
        <div>
          <span className="equipment-stats-label">가동률</span>
          <div className="equipment-utilization">{item.utilization.toFixed(1)}%</div>
        </div>
        <div>
          <span className="equipment-stats-label">마지막 점검일</span>
          <div className="equipment-checked">{item.lastChecked}</div>
        </div>
      </div>
      <span className="breakdown-meter-track">
        <span className="breakdown-meter-fill" style={{ width: `${item.utilization}%` }} />
      </span>
    </article>
  );
}
