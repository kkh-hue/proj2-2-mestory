import type { ReactNode } from "react";
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

export default function Topbar({ title, subtitle, date, onDateChange, action }: Props) {
  return (
    <header className="topbar">
      <div>
        <h1 className="topbar-title">{title}</h1>
        <p className="topbar-subtitle">{subtitle}</p>
      </div>
      <div className="topbar-actions">
        {date && onDateChange && (
          <label className="date-pill date-pill-input" title="이 날짜 기준으로 데이터를 다시 조회합니다">
            <IconCalendar />
            <input
              type="date"
              value={date}
              onChange={(e) => e.target.value && onDateChange(e.target.value)}
              aria-label="조회 기준일"
            />
          </label>
        )}
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
