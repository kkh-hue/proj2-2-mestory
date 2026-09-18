// 리포트 — 디자인 목업 화면 (대시보드/다운타임 분석과 같은 이유로 정적 값을 씀, lib/mockReports.ts 참고).
// 리포트 저장/조회용 백엔드 엔드포인트가 아직 없어 실제 목록 연동은 별도 작업 필요.
import ReportListCard from "../../components/ReportListCard";
import Topbar from "../../components/Topbar";
import { IconChevronDown, IconChevronRight, IconPlus, IconSearch } from "../../components/icons";
import { reportList, sharedReports } from "../../lib/mockReports";

export default function ReportsPage() {
  return (
    <main className="page">
      <Topbar
        title="리포트"
        subtitle="분석 결과를 확인하고 공유하세요."
        action={
          <>
            <label className="search-box">
              <IconSearch />
              <input type="text" placeholder="리포트 검색" aria-label="리포트 검색" />
            </label>
            <button type="button" className="new-analysis-button">
              <IconPlus />
              새 리포트 생성
            </button>
          </>
        }
      />

      <div className="reports-grid">
        <section>
          <div className="reports-list-head">
            <h3>전체 리포트 ({reportList.length})</h3>
            <span className="sort-select">
              최신순
              <IconChevronDown className="filter-chevron" />
            </span>
          </div>
          <div className="report-list">
            {reportList.map((report) => (
              <ReportListCard report={report} key={report.id} />
            ))}
          </div>
        </section>

        <section className="shared-reports-card">
          <div className="reports-list-head">
            <h3>최근 공유된 리포트</h3>
            <a href="#" className="see-all-link">
              전체 보기 <IconChevronRight />
            </a>
          </div>
          <ul className="shared-report-list">
            {sharedReports.map((item, index) => (
              <li key={index}>
                <span className={`shared-avatar shared-avatar-${item.tone}`}>{item.initial}</span>
                <div className="shared-report-body">
                  <span className="shared-report-name">{item.name}</span>
                  <span className="shared-report-title">{item.title}</span>
                  <span className="shared-report-date">{item.date}</span>
                </div>
                <IconChevronRight className="events-row-chevron" />
              </li>
            ))}
          </ul>
        </section>
      </div>
    </main>
  );
}
