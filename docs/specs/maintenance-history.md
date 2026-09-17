# Spec — 정비이력 조회 (F-03, MCP 도구 `get_maintenance_history`)

- 담당: 박민영 · 상태: 구현 완료, 팀 합의 대기
- 코드: `mcp_server/tools/maintenance.py` (`query_maintenance_history`), `mcp_server/server.py` (도구 등록)

## Why

- **페르소나**: 리포트를 만드는 LangChain 에이전트(LLM)
- **상황**: 같은 설비가 자주 멈추면 "최근에 수리했는지, 임시 조치만 했는지"가 원인 추정의 근거가 된다.
- **문제**:
  1. 정비 기록은 673건이라 설비·기간으로 좁혀야 한다.
  2. "오늘" 기준으로 기간을 잡으면 실행할 때마다 결과가 달라져서 평가를 다시 돌릴 수 없다.
  3. 리포트 날짜보다 **뒤의 정비 기록**이 섞이면, 아직 일어나지 않은 일을 근거로 쓰게 된다.
  4. "임시 조치, 재발 가능성 있음" 같은 결과 문구를 LLM이 놓칠 수 있다.
- **측정 지표**: 같은 입력이면 항상 같은 결과 / 리포트 날짜 이후 기록 0건

## Goal

- **해결 목표**: 설비 하나의 "리포트 날짜 기준 최근 N일" 정비 기록을 최신순으로 주고, 재발 위험·재조치 예정 기록을 표시한다.
- **성공 기준**
  - 기준 날짜(reference_date)는 반드시 입력받는다. 없으면 에러로 알린다 (9/17 결정).
  - 기간은 `기준 날짜 - days` ~ `기준 날짜`(양 끝 포함), 미래 기록은 넣지 않는다.
  - 결과 문구 2종을 flags로 100% 표시한다.
- **Out of Scope**: 근본 원인 판단(SKILL.md: 추정으로만 표기) / 정비 일정 추천 / 정비 기록 수정

## What

**Happy Path**
1. 에이전트가 `get_maintenance_history("EQ-001", "2026-09-10")`를 호출한다. (기준 날짜는 보통 정지 로그 조회의 date_to)
2. 설비 ID를 정리하고, 날짜 형식과 days 범위를 확인한다.
3. 해당 설비의 기간 안 기록만 고른다.
4. 최신순(같은 날이면 기록 번호순)으로 정렬하고, 기준 날짜로부터 며칠 전인지(days_before)를 붙인다.
5. 건수·예방/사후 건수·flags 건수·가장 최근 정비일을 요약한다.

**Edge Cases**

| # | 상황 | 처리 방식 |
|---|---|---|
| EC-01 | 결과가 "임시 조치, 재발 가능성 있음" | `RECURRENCE_RISK` 표시 |
| EC-02 | 결과가 "부품 발주 후 재조치 예정" | `PENDING_REWORK` 표시 |
| EC-03 | 기간 안에 기록이 없음 | 0건 + note "최근 N일 동안 정비 기록이 없습니다." |
| EC-04 | 설비 목록에 없는 설비(EQ-058) | 0건 + warnings에 안내 |
| EC-05 | 기준 날짜보다 뒤의 기록 | 넣지 않음 |
| EC-06 | reference_date 없음 / 형식 오류 / equipment_id 없음 | ValueError → 도구는 `{"error", "hint"}` 반환 |
| EC-07 | days가 범위 밖 | 1 ~ 365로 맞춤 |

## How

```
MCP 도구: get_maintenance_history
실행: python -m mcp_server.server (stdio)

입력:
  equipment_id   : 필수. 예 "EQ-001"
  reference_date : 필수. "YYYY-MM-DD"
  days           : 기본 30, 1 ~ 365

출력:
{
  "applied_filters": { "equipment_id", "reference_date", "days", "date_from", "date_to" },
  "warnings": [ 없는 설비 안내 ],
  "summary": {
    "record_count", "preventive_count", "corrective_count",
    "recurrence_risk_count", "pending_rework_count",
    "last_maintenance_date", "last_corrective_date",
    "flag_descriptions", "note"
  },
  "rows": [ { "maintenance_id", "equipment_id", "date", "type",
              "action_taken", "result", "days_before", "flags" } ]   (최신순, 최대 100건)
}

입력 오류: { "error": "한국어 설명", "hint": "입력값을 고쳐서 다시 호출하세요." }
```

- 데이터: `data/maintenance_history.csv`(673건), `data/equipment_master.csv`(없는 설비 확인용)
- 결과 문구 → flag 대응표는 `RESULT_FLAGS` 한 곳에서 관리

## AC (Given-When-Then)

**AC-01 · 기본 30일 조회**
- GIVEN: EQ-001의 9/5 정비 기록(MT-00013, 임시 조치)
- WHEN: `("EQ-001", "2026-09-10")` 조회
- THEN: applied_filters.date_from "2026-08-11", 1건, MT-00013의 flags `["RECURRENCE_RISK"]`, days_before 5

**AC-02 · 긴 기간 요약**
- WHEN: `("EQ-001", "2026-09-10", days=180)` 조회
- THEN: 11건, 예방 4 · 사후 7, recurrence_risk 2, pending_rework 1, last_maintenance_date "2026-09-05", 날짜가 최신순

**AC-03 · 미래 기록 제외**
- WHEN: 어떤 설비든 기준 날짜로 조회
- THEN: 모든 rows의 date ≤ reference_date, days_before ≥ 0

**AC-04 · 기록 없음**
- WHEN: `("EQ-001", "2026-01-01")` 조회
- THEN: 0건, note "최근 30일 동안 정비 기록이 없습니다."

**AC-05 · 없는 설비**
- WHEN: `("eq-058", "2026-09-10")` 조회
- THEN: 0건, warnings에 "EQ-058" 안내 1개

**AC-06 · days 범위**
- WHEN: days=999, days=0
- THEN: applied_filters.days가 각각 365, 1

**AC-07 · 입력 오류**
- WHEN: reference_date 없음 / `"2026/09/10"` / equipment_id 빈 값
- THEN: 함수는 ValueError, MCP 도구는 `error`와 `hint`가 있는 dict를 반환
