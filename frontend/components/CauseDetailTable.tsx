import { useState } from "react";
import { IconChevronRight } from "./icons";
import type { DowntimeCause } from "../types/report";

const tierOf: Record<DowntimeCause["severity"], "critical" | "warning" | "ok" | "unknown"> = {
  "중대": "critical",
  "보통": "warning",
  "경미": "ok",
  "판정 불가": "unknown",
};

function DetailRow({ cause }: { cause: DowntimeCause }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <tr className="detail-row" onClick={() => setOpen((v) => !v)}>
        <td className="events-id">{cause.error_code}</td>
        <td>{cause.description}</td>
        <td>
          <span className={`severity-badge severity-badge-${tierOf[cause.severity]}`}>{cause.severity}</span>
        </td>
        <td>
          <span className="status-badge">{cause.is_confirmed ? "확정" : "확인 필요"}</span>
        </td>
        <td>
          <IconChevronRight className={`events-row-chevron${open ? " events-row-chevron-open" : ""}`} />
        </td>
      </tr>
      {open && (
        <tr className="detail-row-evidence">
          <td colSpan={5}>
            <strong>판단 근거</strong> {cause.evidence}
          </td>
        </tr>
      )}
    </>
  );
}

export default function CauseDetailTable({ causes }: { causes: DowntimeCause[] }) {
  return (
    <section className="events-card">
      <div className="events-head">
        <h3>다운타임 원인 상세</h3>
      </div>
      <div className="events-table-wrap">
        <table className="events-table">
          <thead>
            <tr>
              <th>에러코드</th>
              <th>설명</th>
              <th>심각도</th>
              <th>상태</th>
              <th aria-hidden="true" />
            </tr>
          </thead>
          <tbody>
            {causes.map((cause, index) => (
              <DetailRow cause={cause} key={`${cause.error_code}-${index}`} />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
