# frontend — 진행상황

담당: 강경희 (프론트엔드 · 평가/배포 리드)

Next.js(App Router) + TypeScript 기반 MESTORY 프론트엔드입니다.

사용자가 조회 기간, 라인 ID, 설비 ID를 입력하면 FastAPI Backend의 `POST /report`를 호출하고, 반환된 `DowntimeReport`를 결과 화면에 표시합니다. 라인 ID와 설비 ID는 선택 입력이며, 비워 두면 `null`로 전달하여 전체 데이터를 대상으로 분석합니다.

## 구현된 기능

- [x] 조회 기간(`date_from`/`date_to`) 입력
- [x] 라인 ID 선택 입력
- [x] 설비 ID 선택 입력
- [x] 날짜 범위 validation
- [x] 중복 제출 방지
- [x] 분석 중 화면
- [x] 오류 화면 및 다시 시도
- [x] `POST /report` API 호출
- [x] Backend 응답 기반 결과 화면
- [x] 분석 조건 요약
- [x] 분석된 원인 목록
- [x] `is_confirmed=true` 원인 우선 표시
- [x] severity 표시
- [x] `is_confirmed` 상태 표시
- [x] evidence 펼치기/접기
- [x] `recommended_action` 표시
- [x] `unclassified_count` 기반 데이터 확인 영역
- [x] `confidence_note` 표시
- [x] 새 분석 기능
- [x] 반응형 UI

결과 화면은 분석 조건, 분석된 원인, 권장 조치, 데이터 확인, 분석 참고 사항 순서로 표시합니다. 상단의 `← 새 분석`과 하단의 `← 새 분석 시작`은 입력값·결과·오류를 초기화하고 새 입력 화면으로 돌아갑니다.

## Backend 연결

프론트엔드는 MCP나 LLM을 직접 호출하지 않습니다. `frontend/lib/api.ts`가 Backend API 호출을 담당합니다.

```text
Frontend
  → createReport()
  → NEXT_PUBLIC_API_BASE_URL
  → FastAPI POST /report
  → Backend 내부 분석 흐름
  → DowntimeReport 응답
  → Frontend 렌더링
```

## 환경변수

로컬에서는 `frontend/.env.local`에 다음 값을 설정합니다.

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

- 실제 secret은 저장소에 커밋하지 않습니다.
- `frontend/.env.example`을 복사해서 사용합니다.
- Railway 배포 시에는 배포된 Backend URL을 사용합니다.
- `NEXT_PUBLIC_` 환경변수 변경 후에는 Frontend를 재시작하거나 재빌드해야 합니다.

## 로컬 실행 방법

1. Backend를 먼저 실행합니다.

   프로젝트 루트에서:

   ```powershell
   python -m uvicorn backend.main:app --reload --port 8000
   ```

2. Frontend를 설정하고 실행합니다.

   ```powershell
   cd frontend
   npm ci
   Copy-Item .env.example .env.local
   npm run dev
   ```

   `.env.local`의 `NEXT_PUBLIC_API_BASE_URL`이 Backend 주소를 가리키는지 확인합니다.

3. 브라우저에서 `http://localhost:3000`을 엽니다. 포트가 이미 사용 중이면 Next.js가 다른 포트를 사용할 수 있으므로 터미널에 출력된 주소를 사용합니다.

## 검증 상태

확인된 항목:

- `npm run build`: Next.js production build 성공
- Linting and checking validity of types 통과
- Static page generation 완료
- Frontend → Backend CORS preflight 성공 확인
- `POST /report` 요청 및 HTTP 200 응답 확인
- Backend 응답의 Frontend 결과 렌더링 확인
- `python -m pytest tests/test_report_api.py -q`: 11 passed, 1 deprecation warning
- `git diff --check` 통과

Backend → MCP/LLM → 실제 데이터 정상 분석 전체 E2E는 Frontend 검증 범위와 별도로 확인해야 합니다. Railway 전체 E2E도 별도 확인이 필요합니다.

## 아직 구현하지 않은 기능

- 오류 원인 TOP 3 그래프
- KPI 요약
- PDF 리포트 저장
- 로그인
- 내 분석 기록
- 멀티모달

## Docker / Railway

Frontend는 현재 Docker/docker-compose 서비스에 추가되어 있지 않습니다. Frontend의 Railway 배포 성공 여부는 이 README에서 별도로 검증 완료로 표시하지 않습니다.

## 폴더 구조

```text
frontend/
├── package.json
├── tsconfig.json
├── next.config.js
├── .env.example
├── app/
│   ├── layout.tsx          전체 레이아웃 및 globals.css import
│   ├── page.tsx            입력·분석 중·결과 화면 상태 전환
│   └── globals.css         카드·상태·반응형 스타일
├── components/
│   ├── ChatInput.tsx       조회 기간·라인·설비 입력
│   ├── ChatWindow.tsx      분석 중·오류·결과 상태 표시
│   ├── ReportCard.tsx      DowntimeReport 결과 카드
│   └── CauseList.tsx       원인 목록 및 근거 표시
├── lib/
│   └── api.ts              Backend POST /report 호출
└── types/
    └── report.ts           Backend 요청·응답 타입
```
