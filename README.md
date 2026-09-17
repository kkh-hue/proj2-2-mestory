# MESTORY — 설비 다운타임 원인 분석 리포트 자동 생성 서비스

설비 정지(다운타임) 로그를 분석해 원인·심각도·근거·권장 조치를 담은 리포트를 자동으로 만들어주는 서비스입니다. 최종 원인 확정과 조치 실행은 항상 사람이 하며, 이 서비스는 판단을 돕는 근거와 설명을 제공합니다. 자세한 배경과 요구사항은 [docs/MESTORY_PRD.md](./docs/MESTORY_PRD.md), 기능별 우선순위는 [docs/MESTORY_기능목록.md](./docs/MESTORY_기능목록.md)를 참고하세요.

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
git add .
git commit -m "feat: 로그인 API 구현"
git push -u origin feat/login-api

# 3. GitHub에서 PR 생성 → 조원 리뷰 → approve 후 merge
```

## 충돌(conflict)이 났을 때

PR 화면에 "This branch has conflicts" 가 뜨면:

```bash
git switch main && git pull          # 최신 main 받기
git switch feat/내브랜치
git merge main                       # 충돌 발생 지점이 파일에 표시됨
# 파일 열어 <<<<<<< ======= >>>>>>> 사이에서 남길 내용 선택 후 저장
git add . && git commit              # 충돌 해결 커밋
git push                             # PR이 자동 갱신됨
```

당황하지 말 것 — 충돌은 사고가 아니라 협업의 일상입니다. 막히면 조원 또는 강사를 부르세요.

## 폴더 구조

```
backend/                  FastAPI 백엔드
├── main.py                 진입점 (/health)
├── services/llm.py         LLM 호출 단일 창구 — 출력 계약 검증·재시도/폴백·Langfuse 트레이스
└── README.md                진행상황

mcp_server/                MCP 서버
├── server.py                FastMCP 진입점
├── tools/
│   ├── data_loader.py        CSV 데이터 로딩 (추후 DB 전환 시 여기만 수정)
│   └── downtime.py           조건별 정지 기록 조회
└── README.md                 진행상황

skills/SKILL.md            도메인 지식·판단 기준 (설비 다운타임 원인 분석)
evals/                      평가셋 (dataset.jsonl, 최소 30건)
EVAL_REPORT.md              개선 전후 지표

docs/
├── MESTORY_PRD.md            제품 요구사항 문서
├── MESTORY_기능목록.md       기능 목록 (P0/P1, 범위 밖)
├── SCAFFOLD.md               초기 스캐폴딩 안내
└── specs/                    기능별 Spec 문서 (`_example.md` 형식)

docker-compose.yml / Dockerfile   `docker compose up` 한 줄로 api+db 실행
AGENTS.md / CLAUDE.md       AI 에이전트(Claude Code·Codex 등) 공통 작업 지침
```

## 질문

강사 확인이 필요한 질문은 이 저장소의 **Issues**에 남기고 강사를 멘션하세요.
