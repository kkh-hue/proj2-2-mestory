# backend — 진행상황

담당: 홍민하 (백엔드 · 출력계약 리드)

## 상태

- [x] `/health` 엔드포인트
- [x] `POST /report` — 도메인 엔드포인트 (PRD F-04)
- [x] 요청/응답 Pydantic 모델 정의 (`DowntimeReport`, `DowntimeCause`, `ReportRequest`) — 필수 3
- [x] `services/llm.py` — LLM 호출 단일 창구 구현
  - [x] `create_tool_calling_agent` + `AgentExecutor`로 MCP 도구 호출형 에이전트 구성 (LangGraph 미사용)
  - [x] `load_mcp_tools`로 `mcp_server`에 붙어 도구를 동적으로 불러옴 (도구 이름 하드코딩 없음)
  - [x] 출력 계약 검증 (Pydantic) — 에이전트 응답을 JSON으로 파싱 후 스키마 검증
  - [x] 3단계 재시도/폴백 (① 프롬프트 재시도 → ② 축소 스키마 재시도 → ③ 고정 안전 응답), Docker로 폴백 동작 + **실제 API 키로 end-to-end 성공까지 확인함 (아래 5번 참고)**
  - [x] Langfuse 트레이스 연동 (`langfuse.callback.CallbackHandler`, 키 없으면 자동으로 콜백 생략)
  - [x] `skills/SKILL.md` 전체를 시스템 프롬프트에 그대로 주입 (RAG 아님)
  - [x] 세션별 대화 기록 — 프로토타입 dict (F-07 설계와 동일한 원리, `session_id` 줄 때만 사용)
- [x] 구조화 로그 — request_id, 사용 모델, elapsed_ms, unclassified_count (토큰 사용량은 중복 기록 안 하고 Langfuse 대시보드에서 확인)

## 실행 방법

```bash
cp .env.example .env   # 키 채우기
docker compose up
curl http://localhost:8000/health

curl -X POST http://localhost:8000/report \
  -H "Content-Type: application/json" \
  -d '{"line_id":"LINE-A","date_from":"2026-08-01","date_to":"2026-08-10"}'
```

## TODO / 막힌 것

### 1. 패키지 버전을 여러 개 고정했습니다 (팀 전체에 영향)

`docker build`로 실제 빌드·실행해보니 최신 버전들이 서로 깨져서, `backend/requirements.txt`에 아래처럼 버전을 고정했습니다.

| 패키지 | 문제 |
| --- | --- |
| `mcp<2` | **mcp 2.x부터 `FastMCP`가 `MCPServer`로 이름이 바뀌고 `mcp.server.fastmcp` 모듈 자체가 없어짐.** `mcp_server/server.py`가 `from mcp.server.fastmcp import FastMCP`를 쓰고 있어서 2.x가 깔리면 **MCP 서버 자체가 아예 안 뜹니다.** 필수 조건 5 전체에 영향 — 다들 로컬에 `mcp`를 최신으로 깔아두셨다면 확인해 보세요. |
| `langchain<1.0` | 1.0부터 `create_tool_calling_agent`/`AgentExecutor`가 삭제되고, 대체 API인 `create_agent`는 **내부적으로 LangGraph를 씁니다.** 과제에서 LangGraph를 금지했으니 0.3.x(마지막 pre-1.0)에 고정했습니다. |
| `langchain-mcp-adapters<0.2` | 0.2 이상은 `langchain-core` 1.x 전용 API(`messages.content`)를 참조해서 위 `langchain<1.0`과 같이 쓰면 import 자체가 깨집니다. |
| `pandas` 추가 | `mcp_server/tools`(data_loader, downtime)가 pandas를 쓰는데, backend가 MCP 서버를 같은 컨테이너에서 서브프로세스로 띄우는 구조라 여기 requirements.txt에도 있어야 합니다. |

**Docker로 `/health`, `/report`까지 실제로 띄워서 확인**했습니다. `/report`는 MCP 서브프로세스 연결까지는 성공하고(도구 목록 조회 확인), API 키가 없어서 LLM 호출 단계에서 실패 → 3단계 폴백이 정상적으로 작동해 스키마에 맞는 안전 응답을 반환하는 것까지 확인했습니다.

### 2. (해결됨) mcp_server 도구 3종 등록 완료 — 남은 건 데이터 소스

`mcp_server/server.py`에 `get_downtime_logs`/`get_error_code_info`/`get_maintenance_history` 3종이 전부 등록됐습니다(PR #10). 다만 `mcp_server/tools/data_loader.py`가 아직 로컬 CSV(`data/`)만 읽는데, `data/`는 `.gitignore`에 의도적으로 등록돼 있어서(박민영 님, "chore: ignore data directory") 배포 환경(Docker/Railway)엔 CSV 자체가 없습니다. `scripts/seed_db.py`로 Postgres에 데이터를 넣는 것까지는 준비됐는데, `data_loader.py`가 아직 그 Postgres를 안 읽어서 — **이 부분이 지금 가장 큰 병목**입니다. (`data_loader.py` 파일 자체 주석에도 "나중에 Postgres 쓰게 되면 이 파일만 고치면 된다"고 원래 그렇게 설계돼 있었음.)

### 3. `Dockerfile`이 `backend/`만 복사하고 있었어서 `mcp_server/`, `skills/`도 복사하도록 고쳤습니다

원래는 `backend/`만 이미지에 들어가서 컨테이너 안에서 MCP 서브프로세스를 못 띄우고 SKILL.md도 못 읽는 상태였습니다. `mcp_server/`, `skills/`를 COPY하도록 추가했습니다. **`data/` 폴더가 생기면 `Dockerfile`에 `COPY data/ ./data/` 한 줄을 추가해야 합니다** (지금은 폴더 자체가 없어서 미리 넣으면 빌드가 깨집니다).

### 5. (9/17) 실제 API 키로 첫 end-to-end 테스트 — 프롬프트 템플릿 버그 발견·수정

`OPENROUTER_API_KEY`를 실제 값으로 채우고 로컬 `docs/`의 CSV를 `data/`에 마운트해서(`docker run -v`), 처음으로 진짜 LLM 호출까지 가는 경로를 테스트했습니다. 그동안 키가 계속 비어 있어서 `_build_llm()`이 항상 `RuntimeError`로 즉시 폴백했고, **이 프롬프트 생성 코드는 한 번도 실행된 적이 없었습니다.**

**버그**: `ChatPromptTemplate`은 기본적으로 메시지 문자열을 f-string 템플릿으로 해석해서 `{`/`}`를 변수 자리로 취급합니다. 시스템 프롬프트에 `DowntimeReport.model_json_schema()`(JSON Schema, `{`/`}` 투성이)를 그대로 문자열로 끼워 넣었더니 `Invalid format specifier in f-string template. Nested replacement fields are not allowed.` 에러로 **LLM 호출 전, 프롬프트 생성 단계에서 매번 즉시 실패**하고 있었습니다. 3단계 재시도가 전부 1.7초 안에 끝난 게 그 증거였고, 겉보기엔 정상적인 폴백 응답(200 OK)이라 눈치채기 어려웠습니다.

**수정**: `_escape_braces()` 헬퍼를 추가해서 `schema_json`·`SKILL.md` 내용·`extra_instruction`을 시스템 프롬프트에 끼워 넣기 전에 `{`→`{{`, `}`→`}}`로 이스케이프하도록 고쳤습니다.

**수정 후 실제 테스트 결과** (`LINE-E / EQ-051`, 2026-04-04~04-11, `openai/gpt-4o-mini`):
- 에이전트가 도구 4회 호출(`get_downtime_logs` → `get_error_code_info` → `get_maintenance_history` 등), 1차 시도에 스키마 검증까지 통과
- 소요시간 **10.9초** (PRD 목표 "10초 이내"에 근접 — 여유 있게 보면 조금 초과)
- 원인 6건(E-102, SW-503, SW-501, E-103, S-304, S-301)을 각각 근거·심각도와 함께 반환, 정비이력 기반 재발 가능성까지 `confidence_note`에 반영됨

이 회귀 이후로 `/report`가 실제로 동작하는 걸 코드가 아니라 실행 결과로 확인한 건 이번이 처음입니다 — Pydantic 모델만 있고 "LLM 호출이 안 보인다"던 리뷰 지적이 정확했던 셈입니다.

### 6. 팀 논의가 필요한 부분 (경계 케이스 판단)

- **JSON 파싱 방식**: 에이전트 최종 출력 텍스트에서 `{...}` 구간만 뽑아 JSON으로 파싱하는 단순한 방식(`_extract_json`)을 썼습니다. LLM이 코드펜스 없이 잘 응답하면 문제없지만, 더 엄격하게 하려면 `with_structured_output` 같은 구조화 출력 기능을 쓰는 게 나을 수도 있어요 — 다만 이건 `create_tool_calling_agent` 흐름과는 결이 달라서 지금 방식으로 우선 두었습니다.
- **축소 스키마(2단계 폴백) 응답을 `DowntimeReport`로 감쌀 때** `causes`를 빈 리스트로 두고 `confidence_note`에 요약을 텍스트로 붙였습니다 — 원인 목록이 구조화되어 있지 않다는 뜻인데, 이 방식이 평가셋 채점(F-09)과 잘 맞을지는 확인이 필요합니다.
- **세션 대화 기록**은 프로세스 메모리 dict라 서버 재시작하면 날아갑니다. `POST /report`는 지금 단발 조회 위주라 큰 문제는 아니지만, 강경희 님 프론트(F-07)에서 실제로 후속 질문을 이어가는 UX를 만들 때 이 한계를 감안해야 합니다.
- **`AGENT_MAX_ITERATIONS = 8`**: 도구 호출 무한루프 방지용으로 임의로 잡은 값입니다. 실제 에이전트 동작 보면서 조정이 필요할 수 있어요.
