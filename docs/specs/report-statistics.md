# Spec — KPI 요약 및 주요 다운타임 TOP 3

## Why

- **페르소나**: 특정 기간·라인·설비의 정지 규모와 우선 점검 대상을 빠르게 확인하는 생산관리자.
- **상황**: 기존 LLM 원인 분석과 별도로 로그 기반 수치 요약이 필요하다.
- **문제**: 현재 `DowntimeReport`에는 조회 조건별 원시 집계값이 없다.
- **측정 지표**: 필터 조건·집계 규칙 테스트 통과율 100%.

## Goal

- **성공 기준**: 동일 조건의 기록으로 총 다운타임, 발생 건수, 비계획 다운타임과 오류 코드별 TOP 3를 결정적으로 계산한다.
- **Out of Scope**: 기존 화면/API 연결, LLM 원인 판단, 기존 파일 수정, CSV 업로드, 차트 라이브러리 추가.

## What

**Happy Path**
1. `date_from`, `date_to`, `line_id`, `equipment_id` 조건을 AND로 적용한다.
2. 음수 정지시간·계획 정지·제외 flags 규칙을 적용한다.
3. 총 다운타임·발생 건수·비계획 다운타임을 계산한다.
4. `error_code`별 누적 `downtime_min`을 내림차순 정렬해 최대 3개를 반환한다.

**Edge Cases**

- 빈 결과는 모든 수치 0과 빈 TOP 3를 반환한다.
- 같은 누적 시간은 `error_code` 오름차순으로 안정 정렬한다.
- `unclassified_count`와 `needs_check_count`는 서로 다른 개념으로 유지한다.

## How

- 신규 `backend/services/report_statistics.py`는 DataFrame을 받아 기존 `data_loader`의 컬럼 의미를 따르는 순수 계산 함수를 제공한다.
- 날짜는 `start_time`의 날짜 부분, `line_id`·`equipment_id`는 정확히 일치하는 조건으로 필터링한다.
- 계산 필드: `downtime_min`, `error_code`, `is_planned_stop`, `flags`.
- 신규 Frontend 컴포넌트는 추가 타입의 통계 결과를 표시만 하며 기존 `ReportCard`에 연결하지 않는다.

## AC (Given-When-Then)

**AC-01** GIVEN 날짜·라인·설비 조건 WHEN 계산 THEN 모든 조건을 AND로 적용한다.

**AC-02** GIVEN 필터된 기록 WHEN KPI 계산 THEN 총 다운타임, 발생 건수, 비계획 다운타임을 규칙대로 반환한다.

**AC-03** GIVEN 계획 정지·음수·제외 flags 기록 WHEN TOP 3 계산 THEN 기존 MCP 집계와 동일하게 제외한다.

**AC-04** GIVEN 여러 오류 코드 WHEN 계산 THEN 누적 시간이 큰 순으로 최대 3개를 반환하고 동률은 코드 순으로 유지한다.
