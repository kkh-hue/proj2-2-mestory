# frontend — 진행상황

담당: 강경희 (프론트엔드 · 평가/배포 리드)

Next.js(App Router) + TypeScript로 뼈대만 잡아뒀습니다. `app/`, `components/`, `lib/api.ts`는 전부
주석만 있는 빈 파일이니 원하는 대로 지우거나 다시 짜도 됩니다 — 폴더 구조는 강제가 아니라 제안입니다.

## 폴더 구조

```
frontend/
├── package.json          Next.js/React 의존성
├── tsconfig.json
├── next.config.js
├── .env.example           NEXT_PUBLIC_API_BASE_URL (backend 주소)
├── app/
│   ├── layout.tsx           전체 레이아웃
│   ├── page.tsx              메인 챗봇 페이지 (F-07)
│   └── globals.css
├── components/
│   ├── ChatWindow.tsx        대화 턴 목록
│   ├── ChatInput.tsx          조회 조건 입력
│   ├── ReportCard.tsx          DowntimeReport 카드
│   └── CauseList.tsx            원인 목록
├── lib/
│   └── api.ts                   backend 호출을 모으는 곳 (services/llm.py와 같은 원칙)
└── types/
    └── report.ts                 backend 출력 계약을 그대로 옮긴 타입 (이미 채워둠)
```

## 상태

- [x] 프로젝트 뼈대 (package.json, tsconfig, next.config)
- [x] `types/report.ts` — backend `DowntimeReport`/`DowntimeCause`/`ReportRequest`와 1:1 매칭 (필드 바뀌면 같이 고칠 것)
- [ ] `lib/api.ts` — `POST /report` 호출
- [ ] `app/page.tsx`, `components/*` — 실제 UI
- [ ] Docker/docker-compose에 frontend 서비스 추가 (아직 안 함 — 지금은 `api`, `db`만 있음)

## 실행 방법 (아직 Docker에 안 붙어 있음)

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

## TODO / 막힌 것

(진행하면서 여기에 채워주세요)
