"use client";

import { useState } from "react";
import { printReportAsPdf } from "../lib/reportPdf";
import type { DowntimeReport } from "../types/report";

type Props = { report: DowntimeReport };

/** 독립 컴포넌트이며 현재 결과 화면에는 아직 연결하지 않는다. */
export default function PdfDownloadButton({ report }: Props) {
  const [error, setError] = useState("");

  function handleClick() {
    setError("");
    if (!printReportAsPdf(report)) setError("인쇄 창을 열 수 없습니다. 브라우저의 팝업 차단을 해제한 뒤 다시 시도해 주세요.");
  }

  return <div><button type="button" onClick={handleClick}>PDF로 저장</button>{error && <p role="alert">{error}</p>}</div>;
}
