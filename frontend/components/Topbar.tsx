import type { ReactNode } from "react";
import Link from "next/link";
import { IconCalendar, IconPlus } from "./icons";

type Props = {
  title: string;
  subtitle: string;
  date?: string;
  action?: ReactNode;
};

export default function Topbar({ title, subtitle, date, action }: Props) {
  return (
    <header className="topbar">
      <div>
        <h1 className="topbar-title">{title}</h1>
        <p className="topbar-subtitle">{subtitle}</p>
      </div>
      <div className="topbar-actions">
        {date && (
          // 날짜 검색/필터가 아니라 "이 화면 데이터가 어느 날짜 기준인지" 보여주는
          // 정보 표시다 — 달력 아이콘 때문에 클릭 가능한 검색창처럼 보인다는 피드백이
          // 있어 "기준일"을 앞에 붙여 명확히 했다.
          <span className="date-pill" title="이 화면 데이터의 기준일입니다 (검색/필터 아님)">
            <IconCalendar />
            기준일 {date}
          </span>
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
