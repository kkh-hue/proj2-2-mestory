"use client";

import { useState } from "react";
import EquipmentCard from "./EquipmentCard";
import { IconDashboard } from "./icons";
import type { EquipmentStatus, EquipmentSummaryItem } from "../types/equipment";

const FILTERS: { label: string; status: EquipmentStatus | "all"; dotClassName: string | null }[] = [
  { label: "전체", status: "all", dotClassName: null },
  { label: "정상", status: "정상", dotClassName: "filter-dot-ok" },
  { label: "주의", status: "주의", dotClassName: "filter-dot-warn" },
  { label: "정지", status: "정지", dotClassName: "filter-dot-stop" },
];

export default function EquipmentBoard({ items }: { items: EquipmentSummaryItem[] }) {
  const [active, setActive] = useState<EquipmentStatus | "all">("all");
  const visible = active === "all" ? items : items.filter((item) => item.status === active);

  if (items.length === 0) {
    return <p className="no-causes">등록된 설비가 없습니다.</p>;
  }

  return (
    <>
      <div className="status-filter-row">
        {FILTERS.map((filter) => (
          <button
            type="button"
            key={filter.label}
            className={`status-filter-pill${active === filter.status ? " active" : ""}`}
            onClick={() => setActive(filter.status)}
          >
            {filter.status === "all" ? <IconDashboard /> : <span className={`filter-dot ${filter.dotClassName}`} />}
            {filter.label}
          </button>
        ))}
      </div>

      <div className="equipment-grid">
        {visible.map((item) => (
          <EquipmentCard item={item} key={item.equipment_id} />
        ))}
      </div>
    </>
  );
}
