import Link from "next/link";
import { lineLabel } from "../lib/labels";
import {
  IconChevronRight, IconCheck, IconConveyor, IconEquipment, IconEye, IconFan,
  IconPanel, IconPump, IconRobotArm, IconStamp, IconStopCircle, IconTriangleWarning,
} from "./icons";
import type { EquipmentSummaryItem } from "../types/equipment";

const STATUS_TONE = {
  정상: { className: "status-tone-ok", Icon: IconCheck },
  주의: { className: "status-tone-warn", Icon: IconTriangleWarning },
  정지: { className: "status-tone-stop", Icon: IconStopCircle },
} as const;

// equipment_type은 DB 문구라 정해진 값 집합이 아니다 — 아는 낱말이 보이면 그에 맞는
// 아이콘을 쓰고, 못 알아보면 일반 설비 아이콘으로 무난하게 떨어진다.
const TYPE_ICON: { match: RegExp; Icon: typeof IconEquipment }[] = [
  { match: /프레스|스탬프/, Icon: IconStamp },
  { match: /로봇/, Icon: IconRobotArm },
  { match: /검사|비전|카메라/, Icon: IconEye },
  { match: /컨베이어/, Icon: IconConveyor },
  { match: /펌프/, Icon: IconPump },
  { match: /압축기|팬|송풍/, Icon: IconFan },
  { match: /판넬|패널|제어/, Icon: IconPanel },
];

function iconForType(equipmentType: string) {
  return TYPE_ICON.find(({ match }) => match.test(equipmentType))?.Icon ?? IconEquipment;
}

export default function EquipmentCard({ item }: { item: EquipmentSummaryItem }) {
  const Icon = iconForType(item.equipment_type);
  const { className, Icon: StatusIcon } = STATUS_TONE[item.status];

  return (
    <Link
      href={`/downtime?line_id=${encodeURIComponent(item.line_id)}&equipment_id=${encodeURIComponent(item.equipment_id)}`}
      className={`equipment-card ${className}`}
      style={{ textDecoration: "none", color: "inherit" }}
    >
      <div className="equipment-card-top">
        <span className="equipment-icon">
          <Icon />
        </span>
        <span className="equipment-id">{item.equipment_id}</span>
        <span className="status-badge-pill">
          <StatusIcon /> {item.status}
        </span>
        <IconChevronRight className="events-row-chevron" />
      </div>
      <h4 className="equipment-name">{item.equipment_type}</h4>
      <span className="equipment-line">
        <span className="equipment-line-dot" /> {lineLabel(item.line_id)}
      </span>
      <div className="equipment-stats">
        <div>
          <span className="equipment-stats-label">최근 7일 가동률</span>
          <div className="equipment-utilization">{item.utilization_pct.toFixed(1)}%</div>
        </div>
        <div>
          <span className="equipment-stats-label">마지막 점검일</span>
          <div className="equipment-checked">{item.last_checked ?? "기록 없음"}</div>
        </div>
      </div>
      <span className="breakdown-meter-track">
        <span className="breakdown-meter-fill" style={{ width: `${item.utilization_pct}%` }} />
      </span>
    </Link>
  );
}
