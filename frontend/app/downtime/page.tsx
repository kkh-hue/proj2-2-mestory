"use client";

// 다운타임 분석 — 조건(기간·라인·설비·상태)에 맞는 정지를 원인(에러코드)별로 집계해 보여 준다.
// 데이터는 GET /downtime/analysis (docs/specs/downtime-analysis.md). LLM 원인 분석은 "분석 실행"(/downtime/report).
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import CauseInfoModal from "../../components/CauseInfoModal";
import DateField from "../../components/DateField";
import FilterCard from "../../components/FilterCard";
import Topbar from "../../components/Topbar";
import {
  IconBolt,
  IconCalendar,
  IconChevronRight,
  IconClock,
  IconDots,
  IconEquipment,
  IconGauge,
  IconChart as IconLine,
  IconAlertCircle as IconStatus,
  IconLayers,
  IconPlus,
  IconShield,
  IconTriangleWarning,
} from "../../components/icons";
import { getDowntimeAnalysis, listEquipment } from "../../lib/api";
import { todayKst } from "../../lib/date";
import { equipmentLabel, lineLabel } from "../../lib/labels";
import type { AnalysisCause, AnalysisStatus, DowntimeAnalysis } from "../../types/downtimeAnalysis";
import type { EquipmentSummaryItem } from "../../types/equipment";

const CATEGORY_ICON: Record<string, typeof IconBolt> = {
  전기: IconBolt,
  센서: IconTriangleWarning,
  기계: IconEquipment,
  소프트웨어: IconGauge,
  자재: IconLayers,
};
const RANK_TONES = ["tone-purple", "tone-coral", "tone-amber"] as const;
const STATUS_OPTIONS: { value: AnalysisStatus; label: string }[] = [
  { value: "all", label: "전체 상태" },
  { value: "closed", label: "복구 완료" },
  { value: "open", label: "진행 중" },
];

// 기본 기간은 KST 기준 오늘부터 6일 전까지 (UTC 기준이면 자정~09시에 하루 어긋난다).
function defaultRange() {
  const to = todayKst();
  const [y, m, d] = to.split("-").map(Number);
  const start = new Date(Date.UTC(y, m - 1, d - 6));
  return { from: start.toISOString().slice(0, 10), to };
}

function formatMinutes(min: number) {
  const total = Math.round(min);
  const h = Math.floor(total / 60);
  const m = total % 60;
  return h > 0 ? `${h}h ${String(m).padStart(2, "0")}m` : `${m}m`;
}

// "2026-09-18T14:32:00" → "2026.09.18 14:32" (시간대 변환 없이 문자열 그대로 자른다)
function formatOccurred(iso: string | null) {
  return iso ? `${iso.slice(0, 10).replaceAll("-", ".")} ${iso.slice(11, 16)}` : "-";
}

function toneFor(index: number) {
  return RANK_TONES[index] ?? "tone-gray";
}

export default function DowntimeAnalysisPage() {
  // useSearchParams는 Suspense 경계가 없으면 프로덕션 빌드가 실패한다.
  return (
    <Suspense fallback={null}>
      <DowntimeAnalysisView />
    </Suspense>
  );
}

function DowntimeAnalysisView() {
  const params = useSearchParams();
  const initial = useMemo(defaultRange, []);
  const [dateFrom, setDateFrom] = useState(initial.from);
  const [dateTo, setDateTo] = useState(initial.to);
  // 설비 관리 카드에서 넘어온 경우 그 설비로 미리 걸러 둔다.
  const [lineId, setLineId] = useState(params.get("line_id") ?? "");
  const [equipmentId, setEquipmentId] = useState(params.get("equipment_id") ?? "");
  const [status, setStatus] = useState<AnalysisStatus>("all");

  const [equipment, setEquipment] = useState<EquipmentSummaryItem[]>([]);
  const [data, setData] = useState<DowntimeAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [equipmentError, setEquipmentError] = useState("");
  const [selectedCause, setSelectedCause] = useState<AnalysisCause | null>(null);

  const rangeInvalid = dateFrom > dateTo;

  useEffect(() => {
    listEquipment()
      .then(setEquipment)
      .catch((cause) => setEquipmentError(cause instanceof Error ? cause.message : "설비 목록을 불러오지 못했습니다."));
  }, []);

  useEffect(() => {
    if (rangeInvalid) return;
    let cancelled = false; // 조건을 빠르게 바꿀 때 늦게 도착한 이전 응답이 덮어쓰지 않게
    setLoading(true);
    setError("");
    getDowntimeAnalysis({
      date_from: dateFrom,
      date_to: dateTo,
      line_id: lineId || undefined,
      equipment_id: equipmentId || undefined,
      status,
    })
      .then((result) => !cancelled && setData(result))
      .catch((cause) => !cancelled && setError(cause instanceof Error ? cause.message : "다운타임 분석을 불러오지 못했습니다."))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [dateFrom, dateTo, lineId, equipmentId, status, rangeInvalid]);

  const lines = useMemo(() => Array.from(new Set(equipment.map((e) => e.line_id))).sort(), [equipment]);
  const equipmentOptions = useMemo(
    () => equipment.filter((e) => !lineId || e.line_id === lineId).sort((a, b) => a.equipment_id.localeCompare(b.equipment_id)),
    [equipment, lineId],
  );

  // "분석 실행"(LLM 리포트)으로 지금 걸어 둔 조건을 그대로 넘긴다.
  const reportParams = new URLSearchParams({ date_from: dateFrom, date_to: dateTo });
  if (lineId) reportParams.set("line_id", lineId);
  if (equipmentId) reportParams.set("equipment_id", equipmentId);
  const reportHref = `/downtime/report?${reportParams.toString()}`;

  function changeLine(next: string) {
    setLineId(next);
    // 고른 설비가 새 라인에 없으면 "전체 설비"로 되돌린다
    if (next && equipmentId && !equipment.some((e) => e.equipment_id === equipmentId && e.line_id === next)) {
      setEquipmentId("");
    }
  }

  const empty = data !== null && data.event_count === 0;
  const pageError = error || equipmentError;

  return (
    <main className="page">
      <Topbar
        title="다운타임 분석"
        subtitle="설비별 다운타임 원인과 발생 현황을 분석하여 가동률 향상에 활용하세요."
        action={
          <Link href={reportHref} className="new-analysis-button">
            <IconPlus />
            분석 실행
          </Link>
        }
      />

      <div className="filter-row filter-row-4">
        <FilterCard icon={<IconCalendar />} label="기간">
          <div className="filter-date-range">
            <DateField value={dateFrom} onCommit={setDateFrom} label="조회 시작일" />
            <span>~</span>
            <DateField value={dateTo} onCommit={setDateTo} label="조회 종료일" />
          </div>
        </FilterCard>
        <FilterCard icon={<IconLine />} label="라인">
          <select value={lineId} onChange={(e) => changeLine(e.target.value)} aria-label="라인">
            <option value="">전체 라인</option>
            {lines.map((line) => (
              <option key={line} value={line}>{lineLabel(line)}</option>
            ))}
          </select>
        </FilterCard>
        <FilterCard icon={<IconEquipment />} label="설비">
          <select value={equipmentId} onChange={(e) => setEquipmentId(e.target.value)} aria-label="설비">
            <option value="">전체 설비</option>
            {equipmentOptions.map((item) => (
              <option key={item.equipment_id} value={item.equipment_id}>{equipmentLabel(item)}</option>
            ))}
          </select>
        </FilterCard>
        <FilterCard icon={<IconStatus />} label="상태">
          <select value={status} onChange={(e) => setStatus(e.target.value as AnalysisStatus)} aria-label="상태">
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </FilterCard>
      </div>
      {rangeInvalid && <p className="form-error" role="alert">시작일이 종료일보다 늦습니다. 기간을 다시 선택해 주세요.</p>}

      {loading && !rangeInvalid && (
        <section className="status-card status-loading" aria-live="polite">
          <span className="spinner" /> 다운타임을 집계하고 있습니다.
        </section>
      )}

      {pageError && !loading && (
        <section className="status-card status-error" role="alert">
          <strong>다운타임 분석을 불러오지 못했습니다.</strong>
          <span>{pageError}</span>
        </section>
      )}

      {data && !loading && !pageError && !rangeInvalid && (
        <>
          <div className="dashboard-grid">
            <section className="cause-breakdown-card">
              <div className="card-head">
                <h3>원인별 다운타임 분석</h3>
              </div>
              {empty ? (
                <p className="analysis-empty">조건에 맞는 다운타임이 없습니다.</p>
              ) : (
                <ul className="breakdown-list">
                  {data.breakdown.map((item, index) => {
                    const Icon = CATEGORY_ICON[item.category] ?? IconDots;
                    const tone = item.label === "기타" ? "tone-gray" : toneFor(index);
                    return (
                      <li key={item.label}>
                        <span className={`breakdown-icon ${tone}`} aria-hidden="true">
                          <Icon />
                        </span>
                        <div className="breakdown-main">
                          <span className="breakdown-desc breakdown-desc-label">{item.label}</span>
                          <span className="breakdown-meter-track">
                            <span className={`breakdown-meter-fill ${tone}`} style={{ width: `${item.percent}%` }} />
                          </span>
                        </div>
                        <span className="breakdown-percent">{Math.round(item.percent)}%</span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>

            <section className="insight-panel">
              <div className="card-head">
                <h3>
                  <IconLayers className="insight-title-icon" /> 분석 인사이트
                </h3>
              </div>
              <ul className="insight-list">
                <li>
                  <span className="insight-icon"><IconClock /></span>
                  <div>
                    <span className="insight-label">총 다운타임</span>
                    <div className="insight-value">{formatMinutes(data.total_downtime_min)}</div>
                    <p className="insight-note">선택한 기간 동안 발생한 {data.event_count}건의 총 다운타임입니다.</p>
                  </div>
                </li>
                <li>
                  <span className="insight-icon"><IconGauge /></span>
                  <div>
                    <span className="insight-label">최대 영향 설비</span>
                    <div className="insight-value">{data.top_equipment ? equipmentLabel(data.top_equipment) : "-"}</div>
                    <p className="insight-note">
                      {data.top_equipment
                        ? `${data.top_equipment.equipment_id} · ${formatMinutes(data.top_equipment.downtime_min)}로 가장 많은 다운타임이 발생했습니다.`
                        : "조건에 맞는 다운타임이 없습니다."}
                    </p>
                  </div>
                </li>
                <li>
                  <span className="insight-icon"><IconShield /></span>
                  <div>
                    <span className="insight-label">확인 필요 기록</span>
                    <div className="insight-value">{data.needs_review_count}건</div>
                    <p className="insight-note">시간이 비정상이거나 에러코드 사전에 없는 기록입니다 (비중 계산에서 제외 또는 별도 표기).</p>
                  </div>
                </li>
              </ul>
            </section>
          </div>

          <section className="events-card">
            <div className="events-head">
              <h3>다운타임 원인 상세</h3>
            </div>
            <div className="events-table-wrap">
              <table className="events-table">
                <thead>
                  <tr>
                    <th>원인</th>
                    <th>발생 건수</th>
                    <th>총 시간</th>
                    <th>비중</th>
                    <th>최근 발생</th>
                    <th aria-hidden="true" />
                  </tr>
                </thead>
                <tbody>
                  {data.causes.map((row, index) => {
                    const Icon = CATEGORY_ICON[row.category] ?? IconDots;
                    return (
                      <tr
                        key={row.error_code}
                        className="events-row-clickable"
                        role="button"
                        tabIndex={0}
                        onClick={() => setSelectedCause(row)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            setSelectedCause(row);
                          }
                        }}
                      >
                        <td className="detail-cause-cell">
                          <span className={`breakdown-icon breakdown-icon-sm ${toneFor(index)}`} aria-hidden="true">
                            <Icon />
                          </span>
                          {row.label}
                          <span className="detail-code">{row.error_code}</span>
                        </td>
                        <td>{row.count}건</td>
                        <td>{formatMinutes(row.downtime_min)}</td>
                        <td>{row.percent}%</td>
                        <td>{formatOccurred(row.last_occurred)}</td>
                        <td>
                          <IconChevronRight className="events-row-chevron" />
                        </td>
                      </tr>
                    );
                  })}
                  {empty && (
                    <tr>
                      <td colSpan={6} className="analysis-empty">조건에 맞는 다운타임이 없습니다.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
      {selectedCause && <CauseInfoModal cause={selectedCause} onClose={() => setSelectedCause(null)} />}
    </main>
  );
}
