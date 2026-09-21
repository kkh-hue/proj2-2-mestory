# Spec — Langfuse 트레이스에 요청 출처(user_id) 붙이기

- 담당: 박민영 · 상태: **구현 완료, 팀 합의 대기** (`backend/main.py`는 홍민하 님 파일)
- 코드: `backend/main.py`(`create_report`의 `generate_report` 호출), `tests/test_report_api.py`
- 관련: `EVAL_REPORT.md` 1장 관측 — "`user_id` · `session_id`를 붙였는가"

## Why

- **페르소나**: Langfuse로 서비스를 관측하고 EVAL_REPORT를 채우는 팀원.
- **상황**: Langfuse Users 탭에서 요청을 출처별로 묶어, 평가 트래픽과 실제 사용을 나눠 보고 싶다.
- **문제**:
  1. `user_id`를 붙이는 코드가 평가 스크립트(`score_multimodal.py`, `run_langfuse_eval.py`)뿐이다.
     서비스 요청(`POST /report`)은 `main.py`가 `generate_report()`에 `user_id`를 넘기지 않아 **지금도 비어서 쌓인다.**
  2. 그래서 Users 탭에는 평가(`eval-runner`)만 보이고, 실제 사용은 어디에도 묶이지 않는다.
  3. EVAL_REPORT는 비어 있는 이유를 "붙이기 전에 쌓인 트레이스"로 적었는데, `user_id`에 대해서는 맞지 않는다.
     조회한 400건 중 `user_id` 145건은 전부 평가이고, `session_id`만 있는 44건(189−145)이 서비스 요청으로 추정된다 —
     붙이기 시작한 뒤인데도 `user_id`가 없다.
- **측정 지표**: 배포 이후 `downtime_report` 트레이스 중 `user_id`가 붙은 비율.

## Goal

- **해결 목표**: 서비스 요청에 `user_id="web"`을 붙여 Langfuse에서 평가(`eval-runner`)와 실제 사용(`web`)을 가른다.
- **성공 기준**: 배포 시점 이후 `downtime_report` 트레이스의 100%에 `user_id`가 붙어 있다.
- **Out of Scope**
  - **사람 식별** — 로그인 기능이 없어 누가 보냈는지 알 수 없다. `user_id`는 사람이 아니라 **요청 출처**로 정의한다.
  - **과거 트레이스 소급** — 누가 보낸 요청인지 기록이 없어, 채우면 지어낸 값이 된다.
    배포 시점을 기준선으로 "그 이후 N건 중 N건"을 보고한다.
  - 화면별 세분화(`web-chat`·`web-report` 등) — 필요해지면 별도 Spec.

## What

- **Happy Path**: 화면이 `POST /report`(또는 `/api/agent`) 호출 → `main.py`가 `generate_report(..., user_id="web")` 호출
  → `llm.py`의 `_build_run_config()`가 metadata에 `langfuse_user_id="web"`을 넣음 → Langfuse Users 탭에 `web` 등장.
- **Edge Case**
  - `session_id` 없이 호출해도(API 직접 호출 등) `user_id`는 붙는다 — 두 값은 서로 독립이다.
  - 평가 스크립트는 `generate_report()`를 직접 불러 `user_id="eval-runner"`를 넘긴다 — `main.py`를 거치지 않으므로 이번 변경과 무관하다.
  - Langfuse 키가 없으면 `_build_run_config()`가 빈 설정을 돌려준다 — 기존 동작 그대로(트레이스를 남기지 않음).

## How

- `backend/main.py` `create_report()`의 `generate_report()` 호출에 `user_id="web"` 인자 **1개**만 추가한다.
  `llm.py`는 이미 `user_id`를 받아 `langfuse_user_id`로 붙이므로 고치지 않는다.
- 값은 서버가 정하는 고정 문자열이다. **요청 본문에서 받지 않는다** — 클라이언트가 임의 값을 넣어
  평가 트래픽(`eval-runner`)으로 위장하는 일을 막는다.
- 요청·응답 스키마(`ReportRequest`, `DowntimeReport`)는 바꾸지 않는다 → 프론트 수정 없음.
- 기존 `test_report_contract`는 `generate_report`에 넘긴 인자를 통째로 비교하므로, `user_id`를 따로 꺼내 확인하도록 고친다.

## AC (Given-When-Then)

**AC-01 · 서비스 요청은 `user_id="web"`으로 넘어간다**
- Given `generate_report`를 모의 처리한 앱
- When `session_id`가 있는 요청으로 `POST /report`를 호출하면
- Then `generate_report`가 `user_id="web"`으로 한 번 호출된다

**AC-02 · `session_id`가 없어도 `user_id`는 붙는다**
- Given 같은 앱
- When `session_id` 없이 `POST /api/agent`를 호출하면
- Then `generate_report`가 `user_id="web"`으로 호출된다 (경로·세션 유무와 무관)
