// 설비 관리 (F-07) — backend GET /equipment를 그대로 불러온다.
// 상태·가동률·마지막 점검일은 원본 컬럼이 아니라 backend/db.py가 downtime_log·
// maintenance_history에서 계산한 값이다 (지어낸 값 아님).
"use client";

import { useEffect, useRef, useState } from "react";
import NewAnalysisModal from "../../components/NewAnalysisModal";
import EquipmentBoard from "../../components/EquipmentBoard";
import Topbar from "../../components/Topbar";
import { IconCheck, IconReport, IconStopCircle, IconTriangleWarning } from "../../components/icons";
import { listEquipment, ReportApiError } from "../../lib/api";
import { useLiveTick } from "../../lib/useLiveTick";
import { useNowTick } from "../../lib/useNowTick";
import { todayKst } from "../../lib/date";
import type { EquipmentSummaryItem } from "../../types/equipment";

function formatKstClock(date: Date): string {
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul", hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit",
  }).format(date);
}

function equipmentErrorMessage(cause: unknown): string {
  if (cause instanceof ReportApiError) {
    return "설비 정보를 불러오지 못했습니다.\n다시 시도해 주세요.";
  }
  if (cause instanceof Error && cause.message.includes("10초")) {
    return "설비 정보를 불러오지 못했습니다.\n다시 시도해 주세요.";
  }
  return "네트워크 연결을 확인해 주세요.";
}

export default function EquipmentPage() {
  const [items, setItems] = useState<EquipmentSummaryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [asOf, setAsOf] = useState(todayKst());
  // "정지" 설비가 정확히 언제 끝나는지(active_until) 알면 그 순간에 딱 맞춰 다시
  // 불러온다 — 60초 폴링만 쓰면 최대 60초까지 늦게 "2대 → 1대"로 바뀐다.
  const activeUntils = items.filter((item) => item.status === "정지").map((item) => item.active_until);
  const tick = useLiveTick(asOf, activeUntils);
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
      .catch((cause) => !cancelled && !silent && setError(equipmentErrorMessage(cause)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [asOf, tick]);

  const okCount = items.filter((item) => item.status === "정상").length;
  const warnCount = items.filter((item) => item.status === "주의").length;
  const stopCount = items.filter((item) => item.status === "정지").length;

  // "정지"의 판정 기준·시각이 오늘/과거 날짜에 따라 달라(backend/db.py의 _cutoff) 헷갈리기
  // 쉬워서, 무엇을 보고 정하는지(설비별 다운타임 기록의 종료 시각)까지 풀어 적는다.
  // 원인·예상 종료 시각은 각 설비 카드(EquipmentCard)에 따로 표시된다.
  const isToday = asOf === todayKst();
  const stopNote = isToday
    ? "설비별 다운타임 기록(시작~종료 시각)에서, 종료 시각이 아직 지나지 않은 게 있으면 정지로 셉니다. 카드마다 원인·예상 종료 시각이 표시됩니다."
    : `${asOf} 24:00 시점에 같은 방식으로 판정합니다 — 그때까지 종료 시각이 안 지난 다운타임이 있던 설비입니다.`;
  const warnNote = isToday
    ? "지금 시점 기준 최근 7일 가동률 95% 미만인 설비"
    : `${asOf} 기준 최근 7일 가동률 95% 미만인 설비`;

  // 오늘 화면에서만 의미가 있다 — 과거 날짜는 시간이 안 흐르니 시계를 보여줄 이유가 없다.
  const now = useNowTick(1000);

  const summary = [
    { key: "total", label: "전체 설비", value: `${items.length}대`, note: "등록된 전체 설비 수", Icon: IconReport, tone: "tone-purple" },
    { key: "ok", label: "정상 가동", value: `${okCount}대`, note: "위 '정지'·'점검 필요' 어디에도 안 걸린 설비", Icon: IconCheck, tone: "tone-ok" },
    { key: "warn", label: "점검 필요", value: `${warnCount}대`, note: warnNote, Icon: IconTriangleWarning, tone: "tone-warn" },
    { key: "stop", label: "정지", value: `${stopCount}대`, note: stopNote, Icon: IconStopCircle, tone: "tone-stop" },
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

      {isToday && (
        <p className="live-clock" aria-live="off">
          <span className="live-clock-dot" aria-hidden="true" /> 지금 {formatKstClock(now)} 기준 — "정지" 카드는 실시간으로 갱신됩니다
        </p>
      )}

      {loading && (
        <section className="status-card status-loading" aria-live="polite">
          <span className="spinner" /> 설비 정보를 불러오는 중입니다.
        </section>
      )}
      {!loading && error && (
        <section className="status-card status-error" role="alert">
          <span style={{ whiteSpace: "pre-line" }}>{error}</span>
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
