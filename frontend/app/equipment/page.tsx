// 설비 관리 (F-07) — backend GET /equipment를 그대로 불러온다.
// 상태·가동률·마지막 점검일은 원본 컬럼이 아니라 backend/db.py가 downtime_log·
// maintenance_history에서 계산한 값이다 (지어낸 값 아님).
"use client";

import { useEffect, useRef, useState } from "react";
import NewAnalysisModal from "../../components/NewAnalysisModal";
import EquipmentBoard from "../../components/EquipmentBoard";
import Topbar from "../../components/Topbar";
import { IconCheck, IconReport, IconStopCircle, IconTriangleWarning } from "../../components/icons";
import { listEquipment } from "../../lib/api";
import { useLiveTick } from "../../lib/useLiveTick";
import { todayKst } from "../../lib/date";
import type { EquipmentSummaryItem } from "../../types/equipment";

export default function EquipmentPage() {
  const [items, setItems] = useState<EquipmentSummaryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [asOf, setAsOf] = useState(todayKst());
  const tick = useLiveTick(asOf);
  const loadedFor = useRef<string | null>(null); // 같은 날짜를 다시 조회할 땐 화면을 로딩 상태로 바꾸지 않는다

  useEffect(() => {
    let cancelled = false; // 날짜를 빠르게 바꿀 때 늦게 도착한 이전 응답이 덮어쓰지 않게
    const silent = loadedFor.current === asOf; // 자동 갱신: 깜빡이지 않고, 실패해도 기존 화면을 유지
    if (!silent) {
      setLoading(true);
      setError("");
    }
    listEquipment(asOf)
      .then((data) => {
        if (cancelled) return;
        setItems(data);
        loadedFor.current = asOf;
        setError("");
      })
      .catch((cause) => !cancelled && !silent && setError(cause instanceof Error ? cause.message : "설비 정보를 불러오지 못했습니다."))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [asOf, tick]);

  const okCount = items.filter((item) => item.status === "정상").length;
  const warnCount = items.filter((item) => item.status === "주의").length;
  const stopCount = items.filter((item) => item.status === "정지").length;

  const summary = [
    { key: "total", label: "전체 설비", value: `${items.length}대`, note: "등록된 전체 설비 수", Icon: IconReport, tone: "tone-purple" },
    { key: "ok", label: "정상 가동", value: `${okCount}대`, note: "정상적으로 가동 중인 설비", Icon: IconCheck, tone: "tone-ok" },
    { key: "warn", label: "점검 필요", value: `${warnCount}대`, note: "최근 7일 가동률 95% 미만인 설비", Icon: IconTriangleWarning, tone: "tone-warn" },
    { key: "stop", label: "정지", value: `${stopCount}대`, note: "현재 정지 상태인 설비", Icon: IconStopCircle, tone: "tone-stop" },
  ] as const;

  return (
    <main className="page">
      <Topbar
        title="설비 현황"
        subtitle="라인과 설비 상태를 한눈에 확인하세요."
        date={asOf}
        onDateChange={setAsOf}
        action={<NewAnalysisModal />}
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
