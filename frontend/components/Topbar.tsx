import Link from "next/link";
import { IconCalendar, IconPlus } from "./icons";

type Props = {
  title: string;
  subtitle: string;
  date?: string;
};

export default function Topbar({ title, subtitle, date }: Props) {
  return (
    <header className="topbar">
      <div>
        <h1 className="topbar-title">{title}</h1>
        <p className="topbar-subtitle">{subtitle}</p>
      </div>
      <div className="topbar-actions">
        {date && (
          <span className="date-pill">
            <IconCalendar />
            {date}
          </span>
        )}
        <Link href="/downtime" className="new-analysis-button">
          <IconPlus />
          새 분석 요청
        </Link>
      </div>
    </header>
  );
}
