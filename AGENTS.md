# AGENTS.md

AI 코딩 에이전트(Claude Code, Codex, Cursor 등)가 이 저장소에서 작업할 때 따르는 공통 지침입니다. 어떤 도구를 쓰든 이 문서를 기준으로 합니다.

## 프로젝트 개요

**MESTORY — 설비 다운타임 원인 분석 리포트 자동 생성 서비스.** KDT AI-Human 7기 2차 프로젝트(2조).

설비 정지(다운타임) 로그를 분석해 **원인·심각도·근거·권장 조치**를 담은 리포트를 자동으로 만든다. 질문에 설비 화면 사진을 첨부하면 이미지에서 읽어낸 사실도 근거에 포함한다.

## 기술 스택

| 영역 | 사용 기술 |
|---|---|
| 백엔드 | FastAPI, Pydantic v2, uvicorn |
| 에이전트 | LangChain 0.3.x (`create_tool_calling_agent` + `AgentExecutor`) |
| 도구 | MCP 1.x (FastMCP), stdio 방식 |
| 모델 | OpenRouter 경유 `openai/gpt-5-mini` (vision 지원, ZDR 호환 — 아래 "알려진 문제" 참고) |
| 관측 | Langfuse 4.x |
| 데이터 | pandas / Postgres(psycopg 3) — 환경변수로 전환 |
| 프론트 | Next.js 14, React 18 |
| 테스트 | pytest |

**LangGraph는 쓰지 않는다.** `langchain` 1.0부터 `create_agent`가 내부적으로 LangGraph를 쓰므로 0.3.x에 고정돼 있다.

## 폴더 구조

| 경로 | 내용 |
|---|---|
| `backend/` | FastAPI 서버. `services/llm.py`(LangChain 에이전트 + MCP 연결), `scope.py`(조회 범위 확정), `db.py`(Postgres 저장·집계), `analysis.py`(다운타임 분석 집계) |
| `mcp_server/` | MCP 서버. `tools/*.py`(조회 함수) + `server.py`(MCP 포장) — **분리 유지** |
| `frontend/` | Next.js — 대시보드·다운타임 분석·AI 원인 분석(채팅)·리포트·설비 현황·알림 (모두 백엔드 API 연동) |
| `skills/SKILL.md` | LLM 판단 기준 문서. 프롬프트에 통째로 들어간다 |
| `docs/specs/` | 기능별 Spec (AC 포함) |
| `tests/` | pytest. Spec의 AC와 1:1 |
| `scripts/seed_db.py` | CSV 4개 → Postgres 적재 |
| `evals/` | 평가셋과 측정 기록 |
| `data/` | CSV 4개. **`.gitignore` 대상이라 저장소에 없다** |

## 실행

```bash
pip install -r backend/requirements.txt
pip install pytest                      # requirements에 없음
pytest                                  # 데이터 없으면 일부 skip
python -m mcp_server.server              # MCP 서버 단독 실행(에러 확인용)
```

데이터 소스는 환경변수로 정한다. **자동 전환은 하지 않는다.**

- `MESTORY_DATA_SOURCE=csv`(기본) → `MESTORY_DATA_DIR` 또는 `proj2-2/data`
- `MESTORY_DATA_SOURCE=db` → `DATABASE_URL` 또는 `DATABASE_PUBLIC_URL`

## 협업 규칙

- `main`에 직접 push 금지. 개인 브랜치 → PR → 조원 1명 이상 approve → merge.
- PR 설명은 팀 양식 그대로: `## 변경 요약`(2~3줄) / `## 리뷰 포인트` / `## 체크리스트`(3개).
  체크리스트는 ① 로컬 실행 확인 ② 1명 이상 approve ③ 참고 자료·코드 출처 표기.
- **참고한 자료와 AI 활용 사실은 변경 요약에 한 줄로 적는다.**
- 비밀값(`DATABASE_PUBLIC_URL`, API 키)은 코드·채팅·PR에 쓰지 않는다. `.env`로만 다룬다.
- **`git add .` 금지.** 줄바꿈 규칙이 없어 저장만 해도 수정된 것처럼 보인다. 파일명을 지정해서 add 하고, `git diff --ignore-all-space --stat`가 비어 있으면 실제 변경은 없다.

## Spec 먼저, 구현은 그다음

기능을 에이전트에게 시키기 전에 `docs/specs/{기능명}.md`에 Spec을 먼저 작성하세요. 형식은 `docs/specs/_example.md` 참고 — 다섯 섹션(Why · Goal · What · How · AC)이 다 있어야 에이전트에게 그대로 넘길 수 있습니다.

- **Why**: 페르소나·상황·문제·측정 지표
- **Goal**: 숫자로 된 성공 기준 + Out of Scope
- **What**: Happy Path + Edge Case
- **How**: API·데이터·제약 (에이전트가 임의 결정할 여지를 없앤다)
- **AC**: Given-When-Then 형식, 테스트 코드로 바로 옮길 수 있어야 함

## Out of Scope 원칙

에이전트는 Spec에 없는 기능을 임의로 추가하지 않습니다. "이왕이면"으로 범위를 넓히지 않습니다.

## 완료 기준

테스트(AC 기준) 통과 없이 "완료"라고 보고하지 않습니다.

## 도메인 규칙 (`skills/SKILL.md`와 반드시 일치시킬 것)

- **계획 정지** = `PLANNED_STOP_CODES = {"ETC-602"}` (`mcp_server/tools/downtime.py`). 총 정지시간에는 **포함**, 코드별 집계와 원인 목록에서는 **제외**.
- **원인 미확인** = `UNKNOWN_CAUSE_CODES = {"ETC-604"}`. 흔한 딱지라 목록을 채워 진짜 데이터 오류를 가리지 않게 따로 다룬다.
- **합계**: 음수 정지시간만 합계에서 제외. 빈 코드·미등록 코드는 총계에 포함하되 코드별 집계에서 빼고 '확인 필요'로 분리.
- **심각도는 4개** — `Literal["경미", "보통", "중대", "판정 불가"]` (`backend/services/llm.py`). 근거가 없는 4가지(미등록 코드, 빈 에러코드, 데이터 오류(음수 등), `ETC-604`)는 `판정 불가` + `is_confirmed=false`.
- **조회 도구는 사실만 반환한다. 심각도 판정은 LLM이 한다.**
- `ValueError`는 `{"error", "hint"}` dict로 반환해 에이전트가 멈추지 않게 한다. 설정 오류는 `RuntimeError`(`server.py`가 `ValueError`만 dict로 변환).
- **조회 범위**: `resolve_scope()`(`backend/scope.py`)가 확정한다. 설비ID가 주어지면 그 설비가 속한 라인을 설비 마스터에서 채운다(요청의 라인과 어긋나도 마스터를 따른다). 미등록 설비는 `ScopeError` → 422.

## 버전 고정 (되돌리지 말 것)

| 고정 | 이유 |
|---|---|
| `mcp>=1.29,<2` | 2.x부터 FastMCP가 `MCPServer`로 이름이 바뀌고 `mcp.server.fastmcp`가 없어져 `server.py`(v1 API)가 깨진다 |
| `langchain>=0.3,<1.0` | 1.0부터 `create_tool_calling_agent`/`AgentExecutor`가 사라지고, 대체재 `create_agent`는 LangGraph를 쓴다 |
| `langchain-mcp-adapters>=0.1,<0.2` | 0.2 이상은 langchain-core 1.x 전용 서브모듈을 요구한다 |
| `langfuse>=4.0` | 3.x부터 `CallbackHandler`가 `langfuse.callback` → `langfuse.langchain`으로 이동. 하한을 내리면 **ImportError가 조용히 삼켜져 트레이싱이 꺼진다** |

## 알려진 문제

- **`docker compose up` 한 줄 실행이 깨져 있다.** `data/`가 저장소에 없고 `Dockerfile`이 `data/`·`scripts/`를 복사하지 않아, 컨테이너 안에서 `FileNotFoundError` → 폴백 응답(200 OK)만 나온다. **겉보기엔 동작해 보이니 주의.** (`Dockerfile` 12번 줄에 "data/ 가 생기면 COPY 한 줄 추가할 것"이라고 적혀 있다)
- **F-07(후속 질문 맥락 유지)이 Windows에서 동작하지 않는다.** `session_id`를 넘기면 `Psycopg cannot use the 'ProactorEventLoop' to run in async mode`. MCP 서버는 서브프로세스라 Proactor 루프가, psycopg 비동기는 Selector 루프가 필요해 동시 만족이 불가능하다. Linux 배포에서도 재현되는지 확인 필요.
- **ZDR(Zero Data Retention)을 켠 채로 쓰려면 모델을 가려 써야 한다.** 교육과정 보안 정책이라 ZDR은 끌 수 없다. OpenRouter는 `tools`가 있으면 tool calling 지원 엔드포인트로 한 번 거르고, 그다음 data policy로 또 거른다. `openai/gpt-4o-mini`는 tools를 지원하는 곳이 OpenAI 하나뿐이고 그게 ZDR에서 빠져 **404 `No endpoints found matching your data policy`**가 난다(routing_funnel: 3개 → 1개 → 실패). `openai/gpt-5-mini`는 엔드포인트 4개가 모두 tools를 지원해 ZDR로도 동작한다(Azure 경유). **모델을 바꾸기 전에 `scripts/check_zdr.py`를 먼저 돌릴 것.** 추론 모델(gpt-5 계열)은 `MESTORY_LLM_REASONING_EFFORT`도 함께 설정한다 — 안 하면 추론 토큰이 `max_tokens`를 먼저 써서 리포트 JSON이 잘린다.
