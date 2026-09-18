// 설비 관리 (F-07) — backend GET /equipment를 그대로 불러온다.
// 상태·가동률·마지막 점검일은 원본 컬럼이 아니라 backend/db.py가 downtime_log·
// maintenance_history에서 계산한 값이다 (지어낸 값 아님).
"use client";

import { useEffect, useState } from "react";
import EquipmentBoard from "../../components/EquipmentBoard";
import Topbar from "../../components/Topbar";
import { IconCheck, IconPlus, IconReport, IconStopCircle, IconTriangleWarning } from "../../components/icons";
import { listEquipment } from "../../lib/api";
import type { EquipmentSummaryItem } from "../../types/equipment";

export default function EquipmentPage() {
  const [items, setItems] = useState<EquipmentSummaryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    listEquipment()
      .then(setItems)
      .catch((cause) => setError(cause instanceof Error ? cause.message : "설비 정보를 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, []);

  const okCount = items.filter((item) => item.status === "정상").length;
  const warnCount = items.filter((item) => item.status === "주의").length;
  const stopCount = items.filter((item) => item.status === "정지").length;

  const summary = [
    { key: "total", label: "전체 설비", value: `${items.length}대`, note: "등록된 전체 설비 수", Icon: IconReport, tone: "tone-purple" },
    { key: "ok", label: "정상 가동", value: `${okCount}대`, note: "정상적으로 가동 중인 설비", Icon: IconCheck, tone: "tone-ok" },
    { key: "warn", label: "점검 필요", value: `${warnCount}대`, note: "최근 7일 내 다운타임이 있었던 설비", Icon: IconTriangleWarning, tone: "tone-warn" },
    { key: "stop", label: "정지", value: `${stopCount}대`, note: "현재 정지 상태인 설비", Icon: IconStopCircle, tone: "tone-stop" },
  ] as const;

  return (
    <main className="page">
      <Topbar
        title="설비 관리"
        subtitle="라인과 설비 상태를 한눈에 확인하세요."
        date="2026.09.18"
        action={
          <button type="button" className="new-analysis-button">
            <IconPlus />
            설비 등록
          </button>
        }
      />

      {loading && (
        <section className="status-card status-loading" aria-live="polite">
          <span className="spinner" /> 설비 정보를 불러오는 중입니다.
        </section>
      )}
      {!loading && error && (
        <section className="status-card status-error" role="alert">
          <strong>설비 정보를 불러오지 못했습니다.</strong>
          <span>{error}</span>
        </section>
      )}

      {!loading && !error && (
        <>
          <section className="equipment-summary-grid">
            {summary.map(({ key, label, value, note, Icon, tone }) => (
              <article className="equipment-summary-card" key={key}>
                <span className={`equipment-summary-icon ${tone}`}>
                  <Icon />
                </span>
                <span className="equipment-summary-label">{label}</span>
                <div className="equipment-summary-value">{value}</div>
                <p className="equipment-summary-note">{note}</p>
              </article>
            ))}
          </section>

          <EquipmentBoard items={items} />
        </>
      )}
    </main>
  );
}
