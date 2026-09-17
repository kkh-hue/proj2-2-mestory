# Spec — 정지 로그 조회 (F-01, MCP 도구 `get_downtime_logs`)

- 담당: 박민영 · 상태: 구현 완료, 팀 합의 대기
- 코드: `mcp_server/tools/downtime.py` (`query_downtime_logs`), `mcp_server/server.py` (도구 등록)

## Why

- **페르소나**: 리포트를 만드는 LangChain 에이전트(LLM). 그 뒤에는 "라인이 왜, 얼마나 멈췄는지" 알고 싶은 생산관리자·설비 엔지니어가 있다.
- **상황**: 사용자가 "8/10 LINE-A 리포트 만들어 줘"라고 하면, 에이전트는 해당 기간의 정지 기록부터 봐야 한다.
- **문제**:
  1. 정지 로그는 14,099행이라 LLM에게 전부 줄 수 없다 (비용·길이 한계).
  2. LLM에게 합계·건수를 계산시키면 틀릴 수 있다.
  3. 음수 정지시간, 빈 에러코드, 사전에 없는 코드 같은 **데이터 오류**를 LLM이 그대로 믿고 원인을 지어낼 수 있다 (PRD 게이트: 미등록 코드 환각 0건).
- **측정 지표**: 요약 숫자가 코드 계산값과 100% 일치 / 데이터 오류 기록이 100% 표시됨

## Goal

- **해결 목표**: 조건에 맞는 정지 기록만 골라, **코드가 계산한 사실 요약**과 **주의 표시(flags)**를 함께 돌려준다. 해석·판정은 하지 않는다.
- **성공 기준**
  - 요약(summary)은 limit과 상관없이 조건에 맞는 **전체 기록** 기준으로 계산한다.
  - 데이터 오류 기록 6종(아래 표)은 빠짐없이 flags로 표시한다.
  - 잘못된 입력은 서버를 멈추지 않고 `{"error", "hint"}`로 돌려준다.
- **Out of Scope**: 심각도 판정, 원인 확정, 권장 조치 문구(→ LLM·SKILL.md 담당) / 데이터 수정 / DB 연결(별도 작업)

## What

**Happy Path**
1. 에이전트가 `get_downtime_logs(date_from, date_to, line_id, ...)`를 호출한다.
2. 입력을 정리한다: ID는 앞뒤 공백 제거 + 대문자(`" eq-001 "` → `"EQ-001"`), 날짜는 `YYYY-MM-DD`인지 확인.
3. 모든 조건을 AND로 걸러 낸다. 날짜는 **정지 시작일(start_time)** 기준, 양 끝 포함.
4. 기록마다 설비 종류, 계획정지 여부, flags를 붙인다.
5. 전체 기록으로 요약을 계산하고, 기록은 앞에서부터 limit개만 돌려준다.

**합계 규칙**

| 기록 종류 | 총 정지시간 | 코드별 집계(by_error_code) |
|---|---|---|
| 일반 기록 | 포함 | 포함 |
| 계획 정지(ETC-602) | 포함 (planned로 따로 표시) | 제외 |
| 원인 미확인(ETC-604) | 포함 | 제외 |
| 빈 코드 / 사전에 없는 코드 | 포함 | 제외 (unclassified로 따로 셈) |
| 음수 정지시간 | **제외** | 제외 |

**Edge Cases**

| # | 상황 | 처리 방식 |
|---|---|---|
| EC-01 | 정지시간이 음수 | `NEGATIVE_DOWNTIME` 표시, 합계에서 제외 |
| EC-02 | 에러코드가 비어 있음 | `EMPTY_ERROR_CODE` 표시, unclassified로 셈 |
| EC-03 | 사전에 없는 코드(X-999 등) | `UNREGISTERED_CODE` 표시, unclassified로 셈 |
| EC-04 | 원인 미확인 코드(ETC-604) | `UNKNOWN_CAUSE_CODE` 표시 |
| EC-05 | 설비 목록에 없는 설비(EQ-058) | `UNKNOWN_EQUIPMENT` 표시 |
| EC-06 | 로그의 라인과 설비 목록의 라인이 다름 | `LINE_MISMATCH` 표시 |
| EC-07 | 없는 라인·설비·코드로 조회 | 0건 + warnings에 안내 (0건을 "정지 없음"으로 해석하지 않게) |
| EC-08 | 결과가 limit보다 많음 | 앞에서 limit개만 주고 `truncated: true` |
| EC-09 | 날짜 형식 오류 / 시작일 > 종료일 / 최소 > 최대 | ValueError → 도구는 `{"error", "hint"}` 반환 |
| EC-10 | limit이 범위 밖 | 1 ~ 1000으로 맞춤 |

## How

```
MCP 도구: get_downtime_logs
실행: python -m mcp_server.server (stdio)

입력 (전부 선택):
  date_from, date_to : "YYYY-MM-DD" (정지 시작일 기준, 이 날 포함)
  line_id            : 예 "LINE-A"
  equipment_id       : 예 "EQ-001"
  error_code         : 예 "E-102"
  min_downtime       : 분, 이상
  max_downtime       : 분, 이하
  limit              : 기본 50 (함수 기본 200), 1 ~ 1000

출력:
{
  "applied_filters": { 실제로 적용된 조건 (정리된 값) },
  "warnings": [ 없는 ID 안내 ],
  "summary": {
    "record_count", "total_downtime_min",
    "planned_stop_count", "planned_downtime_min", "unplanned_downtime_min",
    "unclassified_count", "by_error_code",
    "flag_counts", "needs_check_count",
    "needs_check"  (최대 50건, 데이터 오류 먼저),
    "flag_descriptions"
  },
  "total_count", "returned_count", "truncated",
  "rows": [ 원본 컬럼 + equipment_type, is_planned_stop, flags ]
}

입력 오류: { "error": "한국어 설명", "hint": "입력값을 고쳐서 다시 호출하세요." }
```

- 데이터: `data/downtime_log.csv`, `error_code_dict.csv`, `equipment_master.csv` (`data_loader.py`, 환경변수 `MESTORY_DATA_DIR`로 위치 변경 가능)
- 계획 정지 코드 목록 `PLANNED_STOP_CODES = {"ETC-602"}`, 원인 미확인 `UNKNOWN_CAUSE_CODES = {"ETC-604"}`
- stdio 방식이므로 `print()` 금지

## AC (Given-When-Then)

**AC-01 · 조건 조회와 요약**
- GIVEN: 시뮬레이션 데이터
- WHEN: `date_from="2026-08-10", date_to="2026-08-10", line_id="LINE-A"`로 조회
- THEN: record_count 8, total_downtime_min 147.6, planned_stop_count 1, planned_downtime_min 41.9, unclassified_count 1

**AC-02 · 입력 정리**
- GIVEN: 8/10 EQ-001에 X-999 기록 1건
- WHEN: `equipment_id=" eq-001 "`로 조회
- THEN: applied_filters.equipment_id가 "EQ-001", 1건, 그 기록의 flags에 `UNREGISTERED_CODE`

**AC-03 · 데이터 오류 표시**
- GIVEN: 전체 데이터
- WHEN: 조건 없이 조회
- THEN: record_count 14099, total_downtime_min 337695.7, flag_counts = EMPTY_ERROR_CODE 2 · LINE_MISMATCH 3 · NEGATIVE_DOWNTIME 2 · UNKNOWN_CAUSE_CODE 641 · UNKNOWN_EQUIPMENT 1 · UNREGISTERED_CODE 2

**AC-04 · 음수 정지시간**
- GIVEN: 음수 기록 2건 (LOG-014094, LOG-014097)
- WHEN: `max_downtime=-1`로 조회
- THEN: 2건 모두 flags에 `NEGATIVE_DOWNTIME`, total_downtime_min 0

**AC-05 · 없는 ID**
- WHEN: `equipment_id="EQ-999"`로 조회
- THEN: 0건, warnings에 "EQ-999" 안내 1개

**AC-06 · 잘림 표시**
- WHEN: 조건 없이 기본 limit(200)으로 조회
- THEN: returned_count 200, truncated true, summary는 14099건 기준

**AC-07 · limit 범위**
- WHEN: `limit=5000`
- THEN: returned_count 1000

**AC-08 · 복합 조건**
- WHEN: `error_code="M-204", min_downtime=60`
- THEN: total_count 182

**AC-09 · 입력 오류**
- WHEN: `date_from="2026/08/10"` 또는 date_from > date_to 또는 min_downtime > max_downtime
- THEN: 함수는 ValueError, MCP 도구는 `error`와 `hint`가 있는 dict를 반환하고 서버는 계속 동작
