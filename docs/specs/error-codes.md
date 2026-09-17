# Spec — 에러코드 사전 조회 (F-02, MCP 도구 `get_error_code_info`)

- 담당: 박민영 · 상태: 구현 완료, 팀 합의 대기
- 코드: `mcp_server/tools/error_codes.py` (`lookup_error_codes`), `mcp_server/server.py` (도구 등록)

## Why

- **페르소나**: 리포트를 만드는 LangChain 에이전트(LLM)
- **상황**: 정지 기록에 나온 에러코드(E-102 등)의 뜻, 흔한 원인, 보통 정지시간, 기본 심각도를 알아야 리포트를 쓸 수 있다.
- **문제**:
  1. LLM은 모르는 코드(X-999 등)도 그럴듯한 원인을 지어낼 수 있다 (PRD 게이트: 미등록 코드 환각 0건).
  2. 보통 정지시간이 `"10~30"` 같은 글자라서, "실제 정지시간이 상한의 2배 이상인가"(SKILL.md 규칙)를 비교하기 어렵다.
  3. 코드마다 한 번씩 부르면 호출 수와 비용이 늘어난다.
- **측정 지표**: 사전에 없는 코드가 100% `found: false`로 반환됨

## Goal

- **해결 목표**: 코드 여러 개를 한 번에 받아 사전 정보를 돌려주고, 사전에 없는 코드는 **"없음"을 분명하게** 알린다.
- **성공 기준**
  - 사전 24개 코드 모두 `typical_min`, `typical_max` 숫자로 변환된다.
  - 사전에 없는 코드·빈 코드는 원인 정보 없이 `found: false` + 처리 안내 문구만 준다.
  - 계획 정지(ETC-602), 원인 미확인(ETC-604) 코드를 표시한다.
- **Out of Scope**: 최종 심각도 판정(`severity_hint`는 참고값으로 전달만) / 사전 수정·추가 / 코드 추천

## What

**Happy Path**
1. 에이전트가 `get_error_code_info(["E-102", "M-204"])`를 호출한다.
2. 코드를 정리한다: 앞뒤 공백 제거 + 대문자, 중복 제거(들어온 순서 유지).
3. 사전에서 코드마다 정보를 찾는다.
4. 보통 정지시간 `"10~30"`을 숫자 `10.0`, `30.0`으로도 나눠 준다.
5. 찾은 개수와 없는 코드 목록을 함께 돌려준다.

**Edge Cases**

| # | 상황 | 처리 방식 |
|---|---|---|
| EC-01 | 사전에 없는 코드(X-999) | `found: false` + "원인을 추정하지 말고 '판정 불가 — 현장 확인 필요'" 안내 |
| EC-02 | 빈 코드("") | `found: false` + "'로그 기록 누락, 확인 필요'" 안내 |
| EC-03 | 소문자·공백·중복 섞임 | 정리 후 한 번만 조회 |
| EC-04 | 목록 대신 글자 하나("S-303") | 목록 하나로 바꿔서 조회 |
| EC-05 | 빈 목록 / 51개 이상 | ValueError → 도구는 `{"error", "hint"}` 반환 |
| EC-06 | 사전의 범위 글자 모양이 이상함 | 숫자는 `None`, 원래 글자는 그대로 전달 (전체가 멈추지 않음) |
| EC-07 | 계획 정지 코드(ETC-602) | `is_planned_stop: true` |
| EC-08 | 원인 미확인 코드(ETC-604) | `is_unknown_cause: true` |

## How

```
MCP 도구: get_error_code_info
실행: python -m mcp_server.server (stdio)

입력:
  error_codes : 코드 목록 (필수). 예 ["E-102", "M-204"], 최대 50개

출력:
{
  "requested_count": 정리 후 코드 수,
  "found_count":     사전에서 찾은 수,
  "not_found_codes": [ 사전에 없는 코드 ],
  "results": [
    { "error_code", "found": true,
      "category", "description", "typical_cause",
      "typical_duration_min_range", "typical_min", "typical_max",
      "severity_hint", "is_planned_stop", "is_unknown_cause" },
    { "error_code", "found": false, "message" }
  ]
}

입력 오류: { "error": "한국어 설명", "hint": "입력값을 고쳐서 다시 호출하세요." }
```

- 데이터: `data/error_code_dict.csv` (24개)
- 계획 정지·원인 미확인 코드 목록은 `downtime.py`의 `PLANNED_STOP_CODES`, `UNKNOWN_CAUSE_CODES`를 같이 쓴다 (기준을 한 곳에서 관리).

## AC (Given-When-Then)

**AC-01 · 정상 코드 조회**
- GIVEN: 사전에 E-102, M-204가 있음
- WHEN: `["E-102", "M-204"]` 조회
- THEN: found_count 2 / E-102 = 10.0~30.0, 보통 / M-204 = 90.0~240.0, 중대

**AC-02 · 없는 코드와 빈 코드**
- WHEN: `["E-102", "X-999", ""]` 조회
- THEN: requested_count 3, found_count 1, not_found_codes `["X-999", ""]`, 두 코드 결과에 category·typical_cause가 **없음**

**AC-03 · 특수 코드 표시**
- WHEN: `["ETC-602", "ETC-604"]` 조회
- THEN: ETC-602는 is_planned_stop true, ETC-604는 is_unknown_cause true

**AC-04 · 입력 정리**
- WHEN: `[" e-102 ", "E-102"]` 조회
- THEN: requested_count 1, 결과 코드 "E-102"

**AC-05 · 글자 하나 입력**
- WHEN: `"S-303"` 조회
- THEN: found_count 1

**AC-06 · 사전 전체 숫자 변환**
- WHEN: 사전 24개 코드를 모두 조회
- THEN: 모든 결과의 typical_min, typical_max가 None이 아니고 min ≤ max

**AC-07 · 입력 오류**
- WHEN: 빈 목록 또는 서로 다른 코드 51개 조회
- THEN: 함수는 ValueError, MCP 도구는 `error`와 `hint`가 있는 dict를 반환
