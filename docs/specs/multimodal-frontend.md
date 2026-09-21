# Spec — 이미지 첨부 UI (AI 원인 분석 화면)

- 담당: 박민영 · 상태: **작성 완료, 구현 대기**
- 코드: `frontend/app/downtime/ai/page.tsx`, `frontend/app/globals.css`, `frontend/components/icons.tsx`
- 앞선 Spec: [multimodal.md](./multimodal.md) — 백엔드 입력 경로·출력 계약은 거기서 끝났다. 이 문서는 **화면만** 다룬다.
- ⚠️ `frontend/`는 강경희 님 영역 → PR 설명에 측정 근거를 밝히고 리뷰를 받는다.

## Why

- **페르소나**: 현장 설비 엔지니어. 설비가 멈췄고 HMI 패널에 알람이 떠 있다. 그 화면을 휴대폰으로 찍는다.
- **문제**: 백엔드는 이미지를 받을 준비가 **이미 끝나 있다.** `ReportRequest.images`(검증 포함), `DowntimeReport.visual_findings`·`used_image`, DB 저장까지 다 있다. 그런데 **화면에 첨부 수단이 없어서 실제 사용자는 이 기능을 쓸 수 없다.** 지금 이미지를 보내는 건 평가 스크립트(`scripts/score_multimodal.py`)뿐이다.
- **왜 지금 하나 (측정 근거)**: `evals/runs/before.json` 실측에서 이미지를 넣었을 때 `visual_extraction 0.900`, 같은 평가셋에서 이미지만 뺀 대조군은 `0.500`이었다 — **차이 +0.400**. 지연은 `p95 14.2s`로 이미지 게이트(20s) 안이다. 기능이 실제로 일하고 있고 게이트도 통과하는데, 화면이 없어서 못 쓰고 있다.
- **측정 지표**:
  - 첨부한 이미지가 실제로 모델까지 갔는가 — 응답의 `used_image`
  - 이미지에서 읽어낸 사실이 화면에 보이는가 — `visual_findings` 표시 여부

## Goal

- **해결 목표**: `/downtime/ai` 채팅 화면에서 질문에 설비 사진을 첨부하면, 이미지가 근거에 포함된 리포트가 나오고 **무엇을 이미지에서 읽었는지 화면에서 확인**할 수 있다.
- **성공 기준 (숫자)**
  - S-1. 이미지 1~3장을 첨부해 질문하면 응답 `used_image=true`이고, `visual_findings` 항목이 답변 말풍선에 **전부** 표시된다
  - S-2. **이미지 없는 기존 질문은 동작도 모양도 바뀌지 않는다** (회귀 0건)
  - S-3. 백엔드 제한(3장 / 1장 5MB / 합계 10MB / png·jpeg·webp)을 **프론트에서 먼저 막는다.** 제한을 넘는 파일은 서버로 보내지 않는다
  - S-4. `npx tsc --noEmit`과 `npm run build` 통과
- **Out of Scope**
  - `/downtime/report`(분석 실행) 화면 — 이번엔 채팅 화면만
  - 죽은 컴포넌트 `ChatInput.tsx`·`ChatWindow.tsx`·`ReportCard.tsx` — 어느 페이지도 import 하지 않는다(`ff5f966` 이후 방치). **되살리지도, 지우지도 않는다**
  - 카메라로 직접 촬영(`capture` 속성), 드래그앤드롭, 붙여넣기 첨부
  - 이미지 회전·자르기·압축
  - 첨부 이미지를 서버에 저장해 나중에 다시 보기 — base64를 저장하지 않는 것은 [multimodal.md](./multimodal.md) AC-10의 결정이다
  - 프론트 테스트 러너 도입 (`package.json` 건드리지 않음)
  - 모델 라우팅(이미지 있음 → gpt-4o) — 별건

## What

**Happy Path**

1. `/downtime/ai`에서 입력창 왼쪽 **클립 버튼**을 누른다.
2. 파일 선택 창이 열린다 (`accept="image/png,image/jpeg,image/webp"`, 여러 장 선택 가능).
3. 고른 파일이 제한을 통과하면 입력창 위에 **썸네일 칩**으로 쌓인다. 칩마다 제거(×) 버튼이 있다.
4. 질문을 입력하고 전송한다.
5. 파일은 선택 시점에 `FileReader.readAsDataURL`로 data URL로 바뀌어 있고, 전송 때 그 값을 `images` 배열에 담는다.
6. `createReportWithId({ session_id, message, images })` — **`lib/api.ts`는 고치지 않는다.** request를 그대로 직렬화하므로 `images`만 채우면 백엔드까지 간다.
7. 내 말풍선에 질문 텍스트와 첨부 썸네일이 같이 보인다.
8. 답변 말풍선의 기존 `ai-answer-details` 목록에 **"이미지에서 확인한 것"** 행이 추가로 그려진다 (`used_image === true`이고 `visual_findings`가 1건 이상일 때만).
9. 전송 시도 후 첨부 목록은 비워진다.

**이미지를 안 넣은 경우** — 지금과 **완전히 같다.** 첨부 목록이 비어 있으면 `images`를 아예 넣지 않는다(`undefined`). 답변에 새 행도 안 그린다.

**Edge Cases**

| # | 상황 | 처리 방식 |
|---|---|---|
| F-01 | 4장 이상 선택 | **전부 거부**하고 안내. 앞 3장만 자동으로 취하지 않는다 — 어느 장이 빠졌는지 모르는 쪽이 더 나쁘다 |
| F-02 | 1장이 5MB 초과 | 그 파일만 거부 + 파일명·크기 안내. 나머지는 첨부 |
| F-03 | 합계 10MB 초과 | 초과시키는 파일부터 거부 + 안내 |
| F-04 | 지원하지 않는 형식 | 거부 + 안내. **안내 문구에 "아이폰 사진은 HEIC라 png·jpg로 저장해 주세요"를 넣는다** — `accept`로 걸러도 "모든 파일"로 바꿔 고를 수 있다 |
| F-05 | 이미지만 있고 질문이 비어 있음 | **전송 버튼 비활성 유지** (지금과 같은 규칙). 백엔드가 설비·라인을 질문에서 찾으므로 이미지만으로는 422가 난다 |
| F-06 | 첨부 칩의 × 클릭 | 그 장만 목록에서 제거 |
| F-07 | 분석 중(`loading`) | 클립 버튼·× 버튼 모두 비활성 (기존 입력창·전송 버튼과 동일) |
| F-08 | `FileReader` 실패 | 기존 `error` 표시 경로로 "이미지를 읽지 못했습니다" 안내. **전송하지 않는다** |
| F-09 | 프론트를 통과했는데 서버가 422 | 기존 422 처리(`detail` 문자열 그대로 표시)를 그대로 쓴다 — 새로 만들지 않는다 |
| F-10 | `visual_findings`가 `null`·빈 배열 / `used_image=false` | **행 자체를 그리지 않는다.** 빈 칸을 남기지 않는다 |
| F-11 | 새로고침·세션 전환 후 재방문 | 내가 올린 **썸네일은 사라진다**(base64를 서버에 저장하지 않으므로). `visual_findings`는 `reports` 테이블에 남아 **다시 보인다** — `GET /chat/{session_id}`가 함께 돌려준다 |

## How

**고치는 파일 3개. 그 외는 건드리지 않는다.**

| 파일 | 무엇을 |
|---|---|
| `frontend/app/downtime/ai/page.tsx` | 첨부 상태·제한 검사·data URL 변환·썸네일·`visual_findings` 행 |
| `frontend/app/globals.css` | 새 클래스 (PR #41 사고 — JSX만 추가하고 CSS를 빼먹어 날것으로 렌더링된 적 있다) |
| `frontend/components/icons.tsx` | `IconPaperclip` 1개 추가 (기존 `base(props)` 방식 그대로) |

**건드리지 않는 파일과 이유**

| 파일 | 이유 |
|---|---|
| `frontend/types/report.ts` | `images`·`visual_findings`·`used_image`가 **이미 들어 있다** |
| `frontend/lib/api.ts` | `createReportWithId`가 request를 그대로 직렬화한다 |
| `backend/**` | 이미지 경로·검증·저장이 다 끝나 있다 |
| `frontend/package.json` | 새 의존성 없음 |

**제한 상수 — 백엔드와 같은 값을 프론트에도 둔다**

```ts
// backend/main.py의 MAX_IMAGES · MAX_IMAGE_BYTES · MAX_TOTAL_IMAGE_BYTES ·
// ALLOWED_IMAGE_SUBTYPES와 같은 값이다. 한쪽만 고치면 프론트를 통과한 파일이
// 서버에서 422로 튕긴다 — 반드시 같이 고칠 것.
const MAX_IMAGES = 3;
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
const MAX_TOTAL_IMAGE_BYTES = 10 * 1024 * 1024;
const ALLOWED_IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp"];
```

**용량은 `File.size`(원본 바이트)로 잰다.** 백엔드는 base64 글자 수로 재는데, base64는 원본보다 약 33% 크다. 즉 프론트 기준이 더 엄격하므로 **"프론트 통과 → 백엔드 통과"가 보장된다.** 반대로 프론트에서 base64 길이로 재면 경계에서 서로 어긋날 수 있다.

**첨부 상태 타입 — `types/report.ts`를 오염시키지 않는다**

```ts
// 화면에서만 쓰는 값이라 백엔드 계약 타입(types/report.ts)에 넣지 않는다.
type Attachment = { name: string; dataUrl: string };
type ChatTurnView = ChatTurn & { images?: string[] };   // turns state 전용
```

`ChatTurn`은 `GET /chat/{session_id}`의 응답 모양이다. 서버가 주지 않는 필드를 거기 넣으면 "서버에서 올 값"처럼 보인다. 그래서 화면 전용 타입으로 감싼다.

**변환 시점: 파일 선택 때 한 번**
`readAsDataURL`은 비동기다. 전송 버튼을 누른 뒤 변환하면 그 사이 화면이 멈춘 것처럼 보인다. 선택 즉시 변환해 두면 썸네일에도 그대로 쓸 수 있어 파일을 한 번만 읽는다.

**`visual_findings` 표시 위치**

기존 `ai-answer-details` 목록(`기간` / `라인 · 설비` / `분석 참고 사항`)의 **맨 앞**에 한 행을 더한다. 맨 앞인 이유: 이미지를 올린 사용자가 가장 먼저 확인하려는 것이 "내 사진에서 뭘 읽었나"이기 때문이다.

```
<dt>이미지에서 확인한 것</dt>
<dd><ul> … visual_findings 각 항목 … </ul></dd>
```

**새 CSS 클래스** — 기존 이름 규칙(`ai-` 접두사)을 따른다.

| 클래스 | 용도 |
|---|---|
| `.ai-attach-button` | 클립 버튼. `.ai-send-button`과 같은 크기, 배경은 투명 |
| `.ai-attach-row` | 입력창 위 썸네일 칩 줄 |
| `.ai-attach-chip` · `.ai-attach-thumb` · `.ai-attach-remove` | 칩·썸네일·제거 버튼 |
| `.ai-bubble-images` | 내 말풍선 안 썸네일 |
| `.ai-visual-findings` | 답변의 `visual_findings` 목록 |

**제약**
- `<input type="file">`은 화면에서 숨기고(`display:none`) `ref`로 `click()` 한다 — 기본 파일 입력은 팀 디자인과 어긋난다
- 같은 파일을 두 번 연속 골라도 동작해야 한다 → 처리 후 `event.target.value = ""`
- 전송 성공·실패와 무관하게 **전송 시도 후 첨부 목록을 비운다.** 남겨 두면 다음 질문에 의도치 않게 다시 붙는다
- `alert()` 금지. 안내는 기존 `.form-error`(`role="alert"`) 자리에 낸다

## AC (Given-When-Then)

> 프론트 테스트 러너가 없으므로(`package.json`에 jest·vitest 없음) **검증 수단을 AC마다 적는다.**
> 수동 확인은 `evals/images/`의 평가용 이미지를 쓴다 — 정답이 `evals/images/labels.json`에 있어 기대값이 명확하다.

**사전 준비**: 백엔드 실행(`uvicorn backend.main:app`) + `cd frontend && npm run dev` → `http://localhost:3000/downtime/ai`

| AC | Given-When-Then | 검증 수단 |
|---|---|---|
| **AC-F01** | GIVEN 채팅 화면 / WHEN 화면을 연다 / THEN 입력창 왼쪽에 클립 버튼이 있고, 누르면 파일 선택 창이 열린다 | 수동 |
| **AC-F02** | GIVEN `evals/images/normal_e102.png`(라벨: `EQ-006`·`E-102`) / WHEN 첨부하고 "EQ-006 다운타임 원인을 분석해줘" 전송 / THEN 답변에 **"이미지에서 확인한 것"** 행이 있고 그 안에 **`E-102`와 `EQ-006`이 보인다** | 수동 |
| **AC-F03** | GIVEN 첨부 없음 / WHEN 지금과 같은 질문 전송 / THEN 답변 모양이 **지금과 같고** "이미지에서 확인한 것" 행이 없다 | 수동 |
| **AC-F04** | WHEN 이미지 4장 선택 / THEN 4장 모두 첨부되지 않고 "최대 3장" 안내가 뜬다 | 수동 |
| **AC-F05** | WHEN 5MB 초과 파일 선택 / THEN 그 파일만 거부되고 파일명이 포함된 안내가 뜬다 | 수동 |
| **AC-F06** | WHEN 파일 선택 창에서 "모든 파일"로 바꿔 `.gif`(또는 `.heic`) 선택 / THEN 거부 + 지원 형식 안내(HEIC 문구 포함) | 수동 |
| **AC-F07** | GIVEN 이미지 1장 첨부, 질문 칸 비어 있음 / WHEN 전송 버튼을 본다 / THEN **비활성**이다 | 수동 |
| **AC-F08** | GIVEN 2장 첨부 / WHEN 하나의 × 클릭 / THEN 그 장만 사라지고 나머지는 남는다 | 수동 |
| **AC-F09** | GIVEN `evals/images/fail_irrelevant.png`(설비와 무관한 도형) / WHEN 첨부해 전송 / THEN 화면이 깨지지 않는다. `visual_findings`가 비면 행이 **아예 없다** | 수동 |
| **AC-F10** | GIVEN AC-F02를 마친 대화 / WHEN 새로고침 후 같은 세션을 연다 / THEN 내 썸네일은 없지만 **"이미지에서 확인한 것" 행은 그대로 있다** (DB `reports.visual_findings`) | 수동 |
| **AC-F11** | WHEN `npx tsc --noEmit` / THEN 오류 0건 | 기계 |
| **AC-F12** | WHEN `npm run build` / THEN 빌드 성공 | 기계 |
| **AC-F13** | WHEN `.venv\Scripts\python.exe -m pytest -q` / THEN 기존 결과와 같다 (프론트만 고치므로 영향 없음 확인) | 기계 |

**완료 보고 조건**: AC-F11·F12·F13(기계)이 통과하고, AC-F01~F10(수동)을 **실제로 브라우저에서 확인한 뒤**에만 "완료"라고 적는다.
