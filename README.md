# MESTORY — 설비 다운타임 원인 분석 리포트 자동 생성 서비스

설비 정지(다운타임) 로그를 분석해 원인·심각도·근거·권장 조치를 담은 리포트를 자동으로 만들어주는 서비스입니다. 최종 원인 확정과 조치 실행은 항상 사람이 하며, 이 서비스는 판단을 돕는 근거와 설명을 제공합니다. 자세한 배경과 요구사항은 [docs/MESTORY_PRD.md](./docs/MESTORY_PRD.md), 기능별 우선순위는 [docs/MESTORY_기능목록.md](./docs/MESTORY_기능목록.md)를 참고하세요.

## 🚀 배포 (Railway)

- **프론트엔드**: https://mestory-app.up.railway.app — 모든 화면이 실제 백엔드·Postgres에 연결돼 있습니다 (목업 없음)

  | 경로 | 화면 | 데이터 |
  | --- | --- | --- |
  | `/` | 대시보드 | `GET /dashboard` |
  | `/downtime` | 다운타임 분석 (기간·라인·설비·상태 필터) | `GET /downtime/analysis` |
  | `/downtime/ai` | AI 원인 분석 (대화형, 세션 목록, 이미지 첨부) | `POST /report`, `GET /chat/*` |
  | `/downtime/report` | 조건을 지정해 리포트 생성 | `POST /report` |
  | `/reports`, `/reports/[id]` | 리포트 목록·상세 (CSV 다운로드, PDF 저장) | `GET /reports`, `GET /reports/{id}` |
  | `/equipment` | 설비 현황 (정상·주의·정지, 정지 원인·종료 예정 시각) | `GET /equipment` |
  | `/alerts` | 알림센터 | `GET /alerts` |

  대시보드·설비 현황·알림센터·AI 원인 분석은 상단 날짜를 고를 수 있습니다. **오늘**은 현재 시각(KST) 기준으로 계산하고 1분마다 자동 갱신하며, **지난 날짜**는 그날 자정 시점 기준입니다.
- **백엔드 API**: https://mestory.up.railway.app

  | 엔드포인트 | 설명 |
  | --- | --- |
  | `GET /health` | 헬스체크 → `{"status":"ok"}` |
  | `POST /report` (`/api/agent`도 동일) | 리포트 생성 (요청에 `message`·`session_id`·`images`를 줄 수 있음) |
  | `GET /chat/sessions`, `GET /chat/{session_id}` | AI 원인 분석 세션 목록·대화 기록 |
  | `GET /reports`, `GET /reports/{report_id}` | 리포트 목록·상세 |
  | `GET /dashboard`, `GET /alerts`, `GET /equipment` | 화면용 집계 (`as_of=YYYY-MM-DD` 선택) |
  | `GET /downtime/analysis` | 다운타임 분석 집계 |

```bash
curl https://mestory.up.railway.app/health

curl -X POST https://mestory.up.railway.app/report \
  -H "Content-Type: application/json" \
  -d '{"line_id":"LINE-A","equipment_id":"EQ-004","date_from":"2026-01-03","date_to":"2026-01-03"}'
```

배포는 Railway CLI로 합니다 — **백엔드는 저장소 루트에서, 프론트엔드는 `frontend/`에서** 올려야 합니다(반대로 올리면 다른 앱이 서비스에 올라갑니다).

## 🤖 LLM 출력 계약 (필수 조건 3)

`backend/services/llm.py`에서 LangChain `ChatOpenAI`(OpenRouter 경유) + `create_tool_calling_agent`/`AgentExecutor`로 **실제 LLM을 호출**합니다. 응답은 Pydantic(`DowntimeReport`/`DowntimeCause`)으로 스키마 검증하고, 최대 3단계로 시도합니다(① 기본 스키마 → ② 프롬프트를 보강해 같은 스키마로 재시도 → ③ 축소 스키마로 재시도). **3단계가 모두 실패하면 빈 리포트로 감추지 않고 HTTP 503을 반환**하며 리포트·ID를 저장하지 않습니다. 사용자가 준 조건(`equipment_id`·`line_id`·`period`)과 `used_image`는 LLM 출력을 믿지 않고 코드가 덮어씁니다.

- 호출 지점: [backend/services/llm.py](./backend/services/llm.py) — `_build_llm()`, `_generate_with_retries()`, `generate_report()`
- **모델**: `MESTORY_LLM_MODEL`로 정합니다(코드 기본값은 `openai/gpt-4o-mini`, `.env.example`·배포는 `openai/gpt-5-mini`). 교육과정 보안 정책상 ZDR을 끌 수 없어 모델에 따라 OpenRouter가 404를 낼 수 있으니, 모델을 바꾸기 전에 `python scripts/check_zdr.py`로 확인하세요([AGENTS.md](./AGENTS.md) "알려진 문제" 참고).
- **실제 호출 검증**: 위 배포 URL의 `/report`를 직접 호출하면 실제 LLM이 생성한 원인 분석 리포트가 반환됩니다 (Postgres 실데이터 기반). Langfuse에도 트레이스(입력/출력/비용/지연)가 남습니다.
- 상세 테스트 로그·발견한 버그·수정 내역: [backend/README.md](./backend/README.md) 5~7번 항목 참고

## 팀 정보


| 항목     | 내용               |
| -------- | ------------------ |
| 프로젝트 | proj 2 — Mestory |
| 조       | 2                  |

## 조원 소개 — 🏁 첫 과제

**조원 각자가 자기 행을 브랜치 → PR → 리뷰 → merge로 직접 추가하세요.** (전원 필수)
이 첫 PR이 협업 흐름 연습입니다. 같은 표를 여러 명이 수정하면 충돌이 날 수 있는데, 그것까지가 연습입니다 (아래 "충돌이 났을 때" 참고).


| 이름   | GitHub      | 역할                         | 한마디           |
| ------ | ----------- | ---------------------------- | ---------------- |
| 홍민하 | @minhahamin | 백엔드 (출력계약 리드)       | 잘 부탁드립니다! |
| 강경희 | @kkh-hue    | 프론트엔드 · 배포/평가 리드 | 잘 부탁드립니다! |
| 박민영 | @mingdevu   | MCP · 데이터 리드           | 잘 부탁드립니다! |

## 협업 규칙 (필독)

1. **`main`에 직접 push 금지** — 모든 변경은 브랜치 → PR로만 합칩니다.
2. 브랜치명: `feat/{작업내용}` (예: `feat/login-api`, 버그 수정은 `fix/{내용}`)
3. PR은 **조원 1명 이상의 approve를 받은 뒤** merge합니다. 리뷰 없는 merge는 감사 리포트에 잡힙니다.
4. **제출물 = 마감 시점의 `main`** — 마감 시각에 강사가 전체 조 repo에 태그를 일괄 생성합니다. 태그 이후 커밋은 평가 대상이 아닙니다.
5. **커밋은 본인 계정으로**: 자기가 한 작업은 자기 계정으로 커밋해야 이 repo가 본인 포트폴리오 증빙이 됩니다. 함께 작업했다면 커밋 메시지에 `Co-authored-by:`를 추가하세요.
6. 다른 조 저장소도 읽을 수 있습니다 — 보고 배우는 것은 권장, 복사 제출은 금지.

## 📁 필수 조건 매핑 (2차 프로젝트)

| 폴더/파일 | 필수 조건 |
| --- | --- |
| `backend/` (특히 `services/llm.py`) | 필수 2 — FastAPI, LLM 호출 단일 창구 |
| `skills/SKILL.md` | 필수 5 — 도메인 지식·판단 기준 |
| `mcp_server/` | 필수 5 — MCP 서버 |
| `evals/` | 필수 4 — 평가셋 30건 |
| `EVAL_REPORT.md` | 제출물 — 개선 전후 지표 |
| `docker-compose.yml` | 필수 2 — `docker compose up` 한 줄 실행 |

**9/23(수)까지 문제 정의와 `evals/`를 확정하세요.** 추석 연휴 전에 이 둘이 있어야 연휴 동안 각자 진행할 수 있습니다.

각 폴더가 무엇이고 무엇을 채워야 하는지는 **[docs/SCAFFOLD.md](./docs/SCAFFOLD.md)**, 실제 구조는 아래 "폴더 구조" 섹션을 참고하세요.

## 🔑 시크릿 규칙 (위반 시 전원에게 노출됩니다)

- API 키·비밀번호는 **`.env` 파일에만** 두세요. `.env`는 `.gitignore`에 이미 등록되어 커밋되지 않습니다.
- 코드에 키를 직접 적으면 안 됩니다. 이 org는 상호 공개라 **커밋된 키는 7기 전원이 볼 수 있습니다.**
- 모든 push는 **Secret Scan**(GitHub Actions)이 자동 검사합니다. 검사가 ❌ 실패하면 = 키가 커밋된 것입니다. 즉시 강사에게 알리고 **해당 키를 재발급**하세요. (히스토리에서 지워도 유출된 것으로 간주합니다)
- 필요한 키 목록은 `.env.example`에 값 없이 적어 공유하세요.

## 작업 흐름

```bash
# 1. 최신 main에서 작업 브랜치 생성
git switch main && git pull
git switch -c feat/login-api

# 2. 작업 후 커밋·push
git add <바꾼 파일들>          # git add . 는 쓰지 않습니다 (아래 참고)
git commit -m "feat: 로그인 API 구현"
git push -u origin feat/login-api

# 3. GitHub에서 PR 생성 → 조원 리뷰 → approve 후 merge
```

> **`git add .` 금지**: 저장소에 줄바꿈 규칙(`.gitattributes`)이 없어 파일을 저장만 해도 수정된 것처럼 보입니다. 파일명을 지정해서 add 하고, `git diff --ignore-all-space --stat`이 비어 있으면 실제 변경은 없는 겁니다.

## 충돌(conflict)이 났을 때

PR 화면에 "This branch has conflicts" 가 뜨면:

```bash
git switch main && git pull          # 최신 main 받기
git switch feat/내브랜치
git merge main                       # 충돌 발생 지점이 파일에 표시됨
# 파일 열어 <<<<<<< ======= >>>>>>> 사이에서 남길 내용 선택 후 저장
git add <해결한 파일> && git commit   # 충돌 해결 커밋
git push                             # PR이 자동 갱신됨
```

당황하지 말 것 — 충돌은 사고가 아니라 협업의 일상입니다. 막히면 조원 또는 강사를 부르세요.

## 폴더 구조

```
backend/                  FastAPI 백엔드
├── main.py                 라우트 (/health, /report, /chat/*, /reports, /dashboard, /downtime/analysis, /alerts, /equipment)
├── services/llm.py         LLM 호출 단일 창구 — 출력 계약 검증·재시도·Langfuse 트레이스·이미지 입력
├── db.py                   Postgres 접근 (리포트·대화 저장, 대시보드/알림/설비 집계)
├── scope.py                질문·요청에서 조회 범위(라인·설비) 확정
├── analysis.py             다운타임 분석 집계 (DB와 분리한 순수 함수)
└── README.md                진행상황

mcp_server/                MCP 서버 (stdio)
├── server.py                FastMCP 진입점 — 도구 3개(get_downtime_logs·get_error_code_info·get_maintenance_history) 등록
├── tools/
│   ├── data_loader.py        CSV 또는 Postgres에서 표 읽기 (MESTORY_DATA_SOURCE로 전환)
│   ├── downtime.py           조건별 정지 기록 조회·요약
│   ├── error_codes.py        에러코드 사전 조회
│   └── maintenance.py        정비이력 조회
└── README.md                 진행상황

frontend/                  Next.js 14 — 대시보드·다운타임 분석·AI 원인 분석·리포트·설비 현황·알림센터
├── app/                     페이지 (위 표 참고)
├── components/              화면 조각 (Sidebar·Topbar·KpiCard·EquipmentCard·AlertBoard·CauseBreakdown 등)
├── lib/                     api.ts(백엔드 호출 단일 창구)·date.ts·labels.ts·reportCsv.ts·useLiveTick.ts·useNowTick.ts
├── types/                   백엔드 응답과 1:1로 맞춘 타입 (report·dashboard·equipment·alert·downtimeAnalysis)
└── README.md                진행상황

skills/SKILL.md            도메인 지식·판단 기준 (설비 다운타임 원인 분석) — 프롬프트에 통째로 주입
tests/                     pytest — Spec의 AC와 1:1 (데이터가 없으면 일부 skip)
scripts/                   seed_db.py(CSV→Postgres) · check_zdr.py(모델 ZDR 진단) · 멀티모달 평가셋 생성·채점
evals/                      평가셋 (dataset.jsonl 30건, dataset_multimodal.jsonl 10건) · runs/(측정 기록)
EVAL_REPORT.md              개선 전후 지표
tests/                      pytest — docs/specs의 AC와 1:1
scripts/                    seed_db.py(CSV→Postgres) · check_zdr.py · 멀티모달 평가셋 생성·채점 스크립트

data/                       CSV 4개 — .gitignore 대상이라 저장소에 없음 (docs/에 원본 CSV 사본이 있음)

docs/
├── MESTORY_PRD.md            제품 요구사항 문서
├── MESTORY_기능목록.md       기능 목록 (P0/P1, 범위 밖)
├── MESTORY_문제정의서.docx    문제 정의서
├── MESTORY_팀착수체크리스트.docx / MESTORY_평가질문_계획보완10_신규20.xlsx   착수·평가 보조 자료
├── SCAFFOLD.md               초기 스캐폴딩 안내
├── *.csv                     시뮬레이션 데이터 원본 (downtime_log·equipment_master·error_code_dict·maintenance_history)
├── images/                   MCP Inspector 캡처
└── specs/                    기능별 Spec 문서 (`_example.md` 형식)

docker-compose.yml / Dockerfile   `docker compose up`으로 api+db 실행 (프론트엔드는 포함하지 않음 — Railway에 별도 배포, 알려진 문제는 AGENTS.md 참고)
AGENTS.md / CLAUDE.md       AI 에이전트(Claude Code·Codex 등) 공통 작업 지침
```

## 질문

강사 확인이 필요한 질문은 이 저장소의 **Issues**에 남기고 강사를 멘션하세요.
