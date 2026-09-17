// 챗봇형 메인 페이지 — 조회 조건을 입력받아 backend POST /report 결과를 대화형으로 보여준다 (PRD F-07). 담당: 강경희
// 지금은 배포 파이프라인 확인용 최소 플레이스홀더 — ChatWindow/ChatInput/ReportCard로 교체 예정

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function Home() {
  return (
    <main style={{ maxWidth: 640, margin: "80px auto", padding: "0 24px", fontFamily: "system-ui, sans-serif" }}>
      <h1>MESTORY</h1>
      <p>설비 다운타임 원인 분석 서비스 — 프론트엔드는 준비 중입니다 (담당: 강경희).</p>
      <p>
        backend API는 이미 배포되어 있습니다:{" "}
        <a href={API_BASE_URL} target="_blank" rel="noreferrer">
          {API_BASE_URL}
        </a>
      </p>
    </main>
  );
}
