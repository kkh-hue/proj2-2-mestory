# 리포트 조회 범위(scope) 확정 — 질문 속 설비를 조건으로, 세션 후속 질문은 같은 설비로

## Why

- **페르소나**: AI 원인분석 화면에서 특정 설비의 정지 원인을 묻는 현장 담당자.
- **상황**: "EQ-057 컨베이어 다운타임 원인을 분석해줘" 후 "그럼 그 설비는 언제 점검했어?"처럼 이어서 묻는다.
- **문제**:
  1. `message`만 보내면 질문 속 설비를 조건으로 읽지 않아 리포트가 `전체 라인 / 전체 설비`로 저장된다 → 목록의 리포트가 전부 똑같은 제목이 되고, 그 설비의 리포트만 모아 볼 수 없다.
  2. 후속 질문은 설비를 다시 말하지 않으면 또 "전체"로 저장된다.
- **측정 지표**: 새로 저장되는 리포트 중 `전체 라인`·`전체 설비`로 저장되는 비율 0%.

## Goal

- **성공 기준**: AC 11개 통과. `POST /report`는 (설비 또는 라인)이 확정되지 않으면 생성·저장하지 않는다 — `message` 유무와 상관없다.
- **Out of Scope**: 여러 설비를 한 질문에서 동시에 분석, `generate_report`를 직접 호출하는 평가 스크립트(HTTP 경로가 아님)의 변경.

## What

**Happy Path**
1. 사용자가 `message`("EQ-057 … 분석해줘")를 보낸다.
2. 서버가 조건을 이 순서로 확정한다: ① 요청의 `equipment_id`/`line_id` → ② 질문 속 `EQ-숫자`·`LINE-영문`·`A라인` → ③ 같은 세션의 마지막으로 확정된 범위.
3. 설비가 정해지면 그 설비가 속한 라인을 설비 마스터에서 찾아 `line_id`도 같이 채운다.
4. 확정된 범위로 리포트를 생성·저장한다 (`reports.equipment_id`/`line_id`에 실제 값, 대화 턴도 같은 세션에 연결).

**Edge Cases**

| # | 상황 | 처리 |
|---|---|---|
| EC-01 | 질문에도 요청에도 설비·라인이 없고 세션에도 이전 범위가 없다 | 422, 메시지로 "설비(예: EQ-057)나 라인(예: A라인)을 알려 주세요" 안내. 리포트·대화 저장 없음 |
| EC-02 | 질문의 설비가 마스터에 없다 (EQ-999) | 422, "등록되지 않은 설비" 안내 |
| EC-03 | 후속 질문이 다른 설비를 말한다 | 새 설비가 우선, 이후 후속 질문은 새 설비를 따른다 |
| EC-04 | 요청 `equipment_id`와 질문 속 설비가 다르다 | 요청 값이 우선 (화면에서 고른 조건이 정답) |
| EC-05 | 라인만 확정 (설비 없음) | 라인 범위 리포트로 저장 (`line_id`는 실제 라인, `equipment_id`는 `{라인ID} 전체 설비` 예: `LINE-E 전체 설비`) |
| EC-06 | 질문이 `EQ-57`처럼 0을 생략 | `EQ-057`로 정규화 |
| EC-07 | 설비 마스터/DB 조회 실패 | 요청·질문에 명시된 값만으로 진행하고 마스터 검증은 건너뜀; 세션 범위 상속은 안 함 |
| EC-08 | 질문에 설비 종류 이름만 있고("컨베이어") ID가 없다. 세션 범위도 없다 | 후보(라인을 말했으면 그 라인 안에서)가 정확히 1대면 그 설비, 여러 대면 422로 후보 ID를 보여 주며 ID를 적어 달라고 안내, 0대면 종류 이름을 무시 |
| EC-09 | 설비 종류 이름이 있지만 세션 범위가 있다 | 세션 범위를 따른다 ("그 컨베이어는?" 같은 후속 질문) |
| EC-10 | `message` 없이 `line_id`·`equipment_id` 모두 null/생략 | 422 (같은 안내). 화면 폼은 라인 선택을 강제하므로 API를 직접 부를 때만 만난다 |

## How

- `backend/scope.py`: 순수 함수 `resolve_scope(message, line_id, equipment_id, equipment_lines, session_scope) -> (line_id, equipment_id)`. 형식 오류는 `ScopeError(message)`. DB 접근 없음.
- `backend/db.py`: `get_session_scope(session_id)` — 그 세션의 reports 중 `equipment_id like 'EQ-%'` 또는 `line_id like 'LINE-%'`인 가장 최근 행.
- `backend/main.py` `create_report`: 항상 범위를 확정해 `generate_report`에 확정 값을 넘긴다. `message`가 없으면 세션 상속·질문 해석은 하지 않고 요청 값만 검증한다. 이 Spec이 `docs/specs/report-api-connection.md` AC-04의 "인자 그대로 전달, 전부 null도 200" 부분을 대체한다 (설비 마스터로 라인이 채워질 수 있고, 범위가 전혀 없으면 422).
- 설비 종류 추론은 `equipment_types`({설비ID: 종류})를 받아 처리한다.
- 설비→라인 매핑은 `mcp_server.tools.data_loader.load_equipment()` (CSV/DB 모드 공통)을 `asyncio.to_thread`로 읽는다.
- 프론트: 분석 실행 화면과 "새 분석 요청" 모달은 라인을 반드시 고르게 한다 ("전체 라인" 선택지 제거). 설비를 고르면 라인이 따라 채워진다. AI 원인분석 화면은 422 안내 메시지를 그대로 보여 준다.

## AC (Given-When-Then)

**AC-01** GIVEN message="EQ-057 다운타임 원인 분석해줘", 다른 조건 없음 WHEN 범위 해석 THEN equipment_id="EQ-057", line_id=마스터의 EQ-057 라인.

**AC-02** GIVEN message에 "EQ-57" WHEN 해석 THEN "EQ-057"로 정규화된다.

**AC-03** GIVEN message="LINE-B 정지 원인은?" 또는 "B라인 …" WHEN 해석 THEN line_id="LINE-B", equipment_id=None.

**AC-04** GIVEN message에 설비·라인이 없고 세션 범위가 (LINE-C, EQ-057) WHEN 해석 THEN 세션 범위를 그대로 쓴다.

**AC-05** GIVEN 세션 범위가 EQ-057인데 message가 "EQ-012는 어때?" WHEN 해석 THEN EQ-012 (라인은 마스터 값).

**AC-06** GIVEN message에 범위 없음, 요청·세션에도 없음 WHEN 해석 THEN ScopeError, HTTP 422이고 generate_report는 호출되지 않는다.

**AC-07** GIVEN message의 설비가 마스터에 없음 WHEN 해석 THEN ScopeError(422).

**AC-08** GIVEN message 없이 line_id 또는 equipment_id가 있는 요청 WHEN POST /report THEN 그 값이 generate_report로 전달된다 (마스터를 읽었다면 라인이 채워진 값).

**AC-09** GIVEN message="E라인 컨베이어 분석해줘"이고 E라인에 컨베이어가 1대 WHEN 해석 THEN 그 설비가 정해진다. 2대 이상이면 ScopeError에 후보 ID가 들어 있다.

**AC-10** GIVEN message 없이 line_id·equipment_id 모두 없음 WHEN POST /report THEN 422, generate_report 호출 없음.

**AC-11** GIVEN 라인만 확정된 요청 WHEN 리포트 생성 THEN 저장되는 equipment_id는 "{라인ID} 전체 설비"이고 "전체 라인"은 저장되지 않는다.
