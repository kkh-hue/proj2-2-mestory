# frontend — 진행상황

담당: 강경희 (프론트엔드 · 평가/배포 리드)

Next.js 14(App Router) + TypeScript 기반 MESTORY 프론트엔드입니다. 모든 화면이 FastAPI 백엔드를 통해 실제 데이터(Postgres)를 보여줍니다. 프론트엔드는 MCP나 LLM을 직접 호출하지 않고 `lib/api.ts`로 백엔드 API만 부릅니다.

## 화면

| 경로 | 화면 | 백엔드 |
| --- | --- | --- |
| `/` | 대시보드 — KPI·라인별 7일 추이·AI 원인 분석 요약·최근 다운타임 이벤트 | `GET /dashboard` |
| `/downtime` | 다운타임 분석 — 기간·라인·설비·상태 필터, 원인별 집계 | `GET /downtime/analysis` |
| `/downtime/report` | 조건을 지정해 리포트 생성 (조회 기간·라인·설비 입력 → 결과 화면) | `POST /report` |
| `/downtime/ai` | AI 원인 분석 — 대화형, 세션 목록·후속 질문 버튼·이미지 첨부, 날짜 기준 "확인이 필요한 설비" 버튼 | `POST /report`, `GET /chat/*`, `GET /equipment` |
| `/reports`, `/reports/[id]` | 리포트 목록·상세 — 엑셀(CSV) 다운로드, PDF 저장(브라우저 인쇄) | `GET /reports`, `GET /reports/{id}` |
| `/equipment` | 설비 현황 — 정상·주의·정지, 정지 원인·종료 예정 카운트다운·현재 시각 | `GET /equipment` |
| `/alerts` | 알림센터 — 전체·미확인·오늘·다운타임·분석 완료 탭 | `GET /alerts` |

## 날짜와 자동 갱신

대시보드·설비 현황·알림센터·AI 원인 분석은 상단 날짜(`Topbar`)를 고를 수 있습니다.

- **오늘**: 백엔드가 현재 시각(KST) 기준으로 계산합니다. `lib/useLiveTick.ts`가 60초마다 조용히 다시 불러오고(탭이 보일 때만), 설비 현황은 정지 설비의 종료 예정 시각(`active_until`)에 맞춰 즉시 한 번 더 불러옵니다. `lib/useNowTick.ts`는 화면 시계·카운트다운 문구만 1초마다 갱신합니다(재조회 아님).
- **지난 날짜**: 그날 자정 시점 기준으로 고정되며 자동 갱신하지 않습니다.
- 기본 날짜는 `lib/date.ts`의 `todayKst()`(KST)입니다. UTC 날짜를 쓰면 한국 시간 자정~09시에 하루 어긋납니다.

## Backend 연결

`frontend/lib/api.ts`가 백엔드 호출의 단일 창구입니다. 조회 API는 10초, 분석(`POST /report`)은 120초 타임아웃이며 실패는 화면에 오류 상태로 보여줍니다(빈 화면으로 넘기지 않음).

```text
Frontend → lib/api.ts → NEXT_PUBLIC_API_BASE_URL → FastAPI → (DB / MCP / LLM) → 응답 → 렌더링
```

## 환경변수

로컬에서는 `frontend/.env.local`에 다음 값을 설정합니다.

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

- 실제 secret은 저장소에 커밋하지 않습니다.
- `frontend/.env.example`을 복사해서 사용합니다.
- Railway 배포 시에는 배포된 Backend URL(`https://mestory.up.railway.app`)을 사용합니다.
- `NEXT_PUBLIC_` 환경변수 변경 후에는 Frontend를 재시작하거나 재빌드해야 합니다.

## 로컬 실행 방법

1. Backend를 먼저 실행합니다. 프로젝트 루트에서:

   ```powershell
   python -m uvicorn backend.main:app --reload --port 8000
   ```

   Windows에서는 `--reload`가 필요합니다(없으면 psycopg 비동기와 이벤트 루프가 충돌). `.env`는 자동으로 읽히지 않으니 환경변수를 직접 불러온 뒤 실행하세요. 화면 데이터는 `MESTORY_DATA_SOURCE=db`와 `DATABASE_URL`이 필요합니다.

2. Frontend를 설정하고 실행합니다.

   ```powershell
   cd frontend
   npm ci
   Copy-Item .env.example .env.local
   npm run dev
   ```

3. 브라우저에서 `http://localhost:3000`을 엽니다. 포트가 이미 사용 중이면 Next.js가 다른 포트를 사용하므로 터미널에 출력된 주소를 사용합니다.

> `next dev`를 켜 둔 채로 같은 폴더에서 `npm run build`나 `.next` 삭제를 하면 개발 서버가 깨집니다. 타입만 확인할 때는 `npx tsc --noEmit`을 쓰세요.

## 검증 방법

```powershell
cd frontend
npx tsc --noEmit      # 타입 검사
npm run build         # production build
```

프론트엔드에는 자체 테스트 코드가 없고, 화면이 쓰는 백엔드 계약은 프로젝트 루트의 `pytest`(`tests/test_report_api.py` 등)가 검증합니다.

## 아직 구현하지 않은 기능

- 로그인
- PDF 파일 자동 생성 (지금은 브라우저 인쇄로 "PDF로 저장")
- 다운타임 분석(`/downtime`) 화면의 현재 시각 기준·자동 갱신

## Docker / Railway

Frontend는 docker-compose에 포함돼 있지 않고 Railway에 별도 서비스(`frontend`)로 배포합니다(https://mestory-app.up.railway.app). **`frontend/` 폴더에서** `railway up`을 실행해야 합니다. 저장소 루트에서 올리면 백엔드 앱이 프론트엔드 서비스에 올라갑니다.

## 폴더 구조

```text
frontend/
├── package.json / tsconfig.json / next.config.js / .env.example
├── app/
│   ├── layout.tsx              전체 레이아웃(AppShell) 및 globals.css import
│   ├── globals.css             카드·상태·반응형 스타일
│   ├── page.tsx                대시보드
│   ├── downtime/page.tsx       다운타임 분석
│   ├── downtime/report/page.tsx  조건 지정 리포트 생성
│   ├── downtime/ai/page.tsx    AI 원인 분석(대화형)
│   ├── reports/page.tsx        리포트 목록
│   ├── reports/[id]/page.tsx   리포트 상세
│   ├── equipment/page.tsx      설비 현황
│   └── alerts/page.tsx         알림센터
├── components/                 Sidebar·Topbar·KpiCard·TrendChart·AiSummaryCard·EventsTable·
│                               EquipmentBoard/Card·AlertBoard/Row·ReportListCard·NewAnalysisModal·
│                               CauseBreakdown/CauseList/CauseDetailTable/CauseInfoModal·InsightPanel·
│                               ChatInput/ChatWindow/ReportCard 등
├── lib/
│   ├── api.ts                  백엔드 호출 단일 창구
│   ├── date.ts                 todayKst() 등 KST 날짜
│   ├── labels.ts               라인·설비 이름 표시
│   ├── reportCsv.ts            리포트 CSV(엑셀) 다운로드
│   ├── useLiveTick.ts          오늘 화면 자동 갱신 신호
│   └── useNowTick.ts           1초 시계 훅
└── types/                      백엔드 응답 타입 (report·dashboard·equipment·alert·downtimeAnalysis)
```
