import Link from "next/link";
import { lineLabel } from "../lib/labels";
import { useNowTick } from "../lib/useNowTick";
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

// "정지"인 설비가 언제 정상으로 돌아올지(active_until, backend/db.py) 초 단위로 보여준다.
// 실제 상태 전환은 useLiveTick이 그 순간에 서버에 다시 물어봐서 반영하고, 이 문구는
// 그 사이 남은 시간을 화면에서만 계산해 보여주는 카운트다운이다(재조회 아님).
function formatCountdown(activeUntil: string, now: Date): string {
  const end = new Date(activeUntil);
  const hh = String(end.getHours()).padStart(2, "0");
  const mm = String(end.getMinutes()).padStart(2, "0");
  const remainSec = Math.max(0, Math.floor((end.getTime() - now.getTime()) / 1000));
  if (remainSec === 0) return `${hh}:${mm} 종료 예정 · 곧 반영됩니다`;
  const min = Math.floor(remainSec / 60);
  const sec = remainSec % 60;
  const remain = min > 0 ? `${min}분 ${String(sec).padStart(2, "0")}초 후` : `${sec}초 후`;
  return `${hh}:${mm} 종료 예정 · ${remain}`;
}

export default function EquipmentCard({ item }: { item: EquipmentSummaryItem }) {
  const Icon = iconForType(item.equipment_type);
  const { className, Icon: StatusIcon } = STATUS_TONE[item.status];
  const showCountdown = item.status === "정지" && item.active_until;
  // 카운트다운이 필요 없는 카드까지 57개가 전부 1초마다 리렌더할 필요는 없다 —
  // 해당 없는 카드는 사실상 안 도는 것과 같은 긴 주기로 묶어 둔다.
  const now = useNowTick(showCountdown ? 1000 : 3_600_000);

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
      {item.status === "정지" && (item.active_cause || item.active_until) && (
        <div className="equipment-active-info">
          {/* 왜 정지인지 — downtime_log의 에러코드를 사람이 읽는 이름으로(없으면 코드 그대로) */}
          {item.active_cause && <span className="equipment-active-cause">{item.active_cause} 관련 정지</span>}
          {/* 언제 풀리는지 — 이 설비의 다운타임 기록 중 아직 안 끝난 것의 종료 시각 기준
              (끝이 안 정해진 다운타임이면 이 줄은 안 뜬다) */}
          {showCountdown && item.active_until && (
            <span className="equipment-active-until">{formatCountdown(item.active_until, now)}</span>
          )}
        </div>
      )}
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
