import type { ReactNode } from "react";

export default function FilterCard({ icon, label, children }: { icon: ReactNode; label: string; children: ReactNode }) {
  return (
    <div className="filter-card">
      <div className="filter-icon">{icon}</div>
      <div className="filter-body">
        <span className="filter-label">{label}</span>
        <div className="filter-value">{children}</div>
      </div>
    </div>
  );
}
