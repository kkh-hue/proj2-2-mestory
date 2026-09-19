"use client";

import { useEffect, useState } from "react";

// 직접 타이핑하는 중에는 연도가 덜 입력된 값("31526-03-15" 등)이 onChange로 넘어온다.
// 4자리 연도(2000~2100)가 완성된 날짜만 부모에 알리고, 입력 중 값은 draft로 들고 있어
// 부모 값으로 입력창이 되돌려지지 않게 한다 (Topbar의 기준일 입력과 같은 규칙).
function isCompleteDate(value: string) {
  const year = Number(value.slice(0, 4));
  return /^\d{4}-\d{2}-\d{2}$/.test(value) && year >= 2000 && year <= 2100;
}

export default function DateField({
  value,
  onCommit,
  label,
}: {
  value: string;
  onCommit: (value: string) => void;
  label: string;
}) {
  const [draft, setDraft] = useState(value);
  useEffect(() => setDraft(value), [value]);

  return (
    <input
      type="date"
      value={draft}
      aria-label={label}
      onChange={(e) => {
        setDraft(e.target.value);
        if (isCompleteDate(e.target.value)) onCommit(e.target.value);
      }}
    />
  );
}
