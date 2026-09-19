"use client";

import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { IconCalendar, IconPlus } from "./icons";

type Props = {
  title: string;
  subtitle: string;
  // "YYYY-MM-DD". onDateChange와 같이 줘야 진짜 달력 입력(input type=date)이 뜬다 —
  // 그냥 문자열만 보여주던 전 버전은 "날짜 검색처럼 보이는데 안 눌린다"는 혼란을 줬다.
  date?: string;
  onDateChange?: (value: string) => void;
  action?: ReactNode;
};

// 직접 타이핑하는 중에는 연도가 덜 입력된 값(예: "31526-03-15", "0002-03-15")이 onChange로
// 넘어온다. 그대로 조회하면 백엔드가 422를 돌려줘 오류 화면이 뜨므로, 4자리 연도가
// 완성된 값만 기준일로 받는다.
function isCompleteDate(value: string) {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) && Number(value.slice(0, 4)) >= 2000 && Number(value.slice(0, 4)) <= 2100;
}

// 입력 중인 값(draft)은 여기서만 들고 있고, 완성된 날짜일 때만 부모에 알린다.
// 부모 값을 바로 value로 물리면 타이핑 도중 입력창이 원래 날짜로 되돌려진다.
function DatePill({ date, onDateChange }: { date: string; onDateChange: (value: string) => void }) {
  const [draft, setDraft] = useState(date);
  useEffect(() => setDraft(date), [date]);

  return (
    <label className="date-pill date-pill-input" title="이 날짜 기준으로 데이터를 다시 조회합니다">
      <IconCalendar />
      <input
        type="date"
        value={draft}
        onChange={(e) => {
          setDraft(e.target.value);
          if (isCompleteDate(e.target.value)) onDateChange(e.target.value);
        }}
        aria-label="조회 기준일"
      />
    </label>
  );
}

export default function Topbar({ title, subtitle, date, onDateChange, action }: Props) {
  return (
    <header className="topbar">
      <div>
        <h1 className="topbar-title">{title}</h1>
        <p className="topbar-subtitle">{subtitle}</p>
      </div>
      <div className="topbar-actions">
        {date && onDateChange && <DatePill date={date} onDateChange={onDateChange} />}
        {action ?? (
          <Link href="/downtime" className="new-analysis-button">
            <IconPlus />
            새 분석 요청
          </Link>
        )}
      </div>
    </header>
  );
}
