# Spec — 다운타임 분석 화면 (실데이터)

`/downtime` 화면은 지금까지 `frontend/lib/mockDowntimeAnalysis.ts`의 고정값(기준일 2026.09.18, "분석 신뢰도 87%")을 보여 주는 목업이었다. 이 Spec은 그 화면을 `downtime_log`·`error_code_dict` 실데이터 집계로 바꾼다. LLM은 쓰지 않는다 (LLM 원인 분석은 `/downtime/report`, `/downtime/ai`의 몫).

## Why

- **페르소나**: 생산 라인 관리자 (설비 정지 현황을 기간·라인·설비별로 훑어보고 어디부터 손댈지 정하는 사람)
- **상황**: AI 분석을 돌리기 전에, 기간 안에서 어떤 원인이 다운타임을 가장 많이 만들었는지 숫자로 먼저 보고 싶다.
- **문제**:
  1. 화면의 기간·원인·시간이 전부 고정값이라 조건을 바꿔도 아무것도 안 변한다.
  2. "분석 신뢰도 87%"는 어떤 데이터에서도 계산되지 않는 값이다 (근거 없는 수치).
  3. 필터(기간/라인/설비/상태)가 눌러지지 않는 그림이다.
- **측정 지표**: 필터 변경 후 결과 갱신 2초 이내 / 화면의 모든 숫자가 `downtime_log` 직접 집계와 일치

## Goal

- **해결 목표**: 조회 조건(기간·라인·설비·상태)에 맞는 다운타임을 원인(에러코드)별로 집계해 보여 준다.
- **성공 기준**:
  - 원인별 비중 합계 = 100% (반올림 오차 ±0.1 이내)
  - 화면 총 다운타임 = 같은 조건의 `sum(downtime_min)` (0 이하 값 제외)
  - 조건 변경 → 재조회 결과 표시까지 2초 이내 (로컬 DB 기준)
- **Out of Scope**: LLM 호출·AI 요약, 원인 행 클릭 시 상세 화면, 엑셀 내보내기, 시간대별(시프트별) 분석, 페이지네이션

## What

**Happy Path**
1. 화면 진입 → 기본 조건(최근 7일, 오늘 포함 / 전체 라인 / 전체 설비 / 전체 상태)으로 자동 조회한다.
2. 사용자가 기간·라인·설비·상태 중 하나를 바꾸면 즉시 다시 조회한다.
3. **원인별 다운타임 분석**: 다운타임 시간이 큰 상위 4개 원인 + 나머지를 묶은 "기타"의 비중(막대).
4. **분석 인사이트**: 총 다운타임 / 최대 영향 설비 / 확인 필요 기록 건수.
5. **다운타임 원인 상세**: 원인(에러코드)별 발생 건수·총 시간·비중·최근 발생 시각 표.

**Edge Cases**

| # | 상황 | 처리 방식 |
|---|---|---|
| EC-01 | 조건에 맞는 기록이 0건 | "조건에 맞는 다운타임이 없습니다" 빈 상태 표시. 총 0m, 최대 영향 설비 "-" |
| EC-02 | `downtime_min` ≤ 0 이거나 NULL인데 종료된 행 (데이터 오류) | 시간·비중 계산에서 제외하고 "확인 필요 기록"에 건수로 센다 |
| EC-03 | `error_code_dict`에 없는 코드 | 삭제하지 않고 `"{코드} (사전 미등록)"`으로 집계, "확인 필요 기록"에도 센다 |
| EC-04 | `date_to`가 오늘(KST)보다 미래 | 오늘 끝까지로 자른다 (시뮬레이션 데이터에 미래 시각 행이 섞여 있음) |
| EC-05 | `date_from` > `date_to` | 프론트는 조회하지 않고 안내 문구, API는 422 |
| EC-06 | 날짜 입력 중(연도 미완성) | 완성된 날짜(2000~2100년)만 조건으로 반영 |
| EC-07 | 조회 실패 | 오류 카드 + 조건을 바꾸면 자동으로 다시 시도 (오류에 갇히지 않음) |
| EC-08 | 조건을 빠르게 연속 변경 | 늦게 도착한 이전 응답은 무시 |
| EC-09 | 종료 안 된(`end_time` NULL) 진행 중 정지 | 발생 건수엔 포함, 시간 합계엔 미포함 (아직 시간이 확정되지 않음). 상태 필터 "진행 중"으로 따로 볼 수 있다 |

## How

```
GET /downtime/analysis
쿼리 (모두 선택):
  date_from   YYYY-MM-DD   기본: date_to - 6일
  date_to     YYYY-MM-DD   기본: 오늘(KST). 오늘보다 미래면 오늘로 자른다
  line_id     string       예: LINE-A
  equipment_id string      예: EQ-021
  status      all | closed | open   기본 all  (closed=복구 완료, open=진행 중)

응답 200:
{
  "date_from": "2026-09-14", "date_to": "2026-09-20",
  "event_count": int,                    // 조건에 맞는 정지 건수 (EC-02 제외 후)
  "total_downtime_min": float,
  "top_equipment": { "equipment_id", "equipment_type", "downtime_min" } | null,
  "needs_review_count": int,             // EC-02 + EC-03
  "breakdown": [ { "label", "category", "percent" } ],   // 상위 4 + "기타", 시간 기준 내림차순
  "causes": [ { "error_code", "label", "category", "count",
                "downtime_min", "percent", "last_occurred" (ISO) } ]  // 시간 기준 내림차순
}
응답 실패: 422 (date_from > date_to, 날짜/status 형식 오류)
```

- 비중(percent) = 원인 시간 / 총 시간 × 100 (소수 1자리). 총 시간 0이면 전부 0.
- `breakdown`의 "기타"는 5번째 이후 원인의 합. 원인이 4개 이하면 "기타"를 만들지 않는다.
- 집계 기준 시각은 `start_time` (`date_from` 0시 이상, `date_to` 다음날 0시 미만).
- 집계·상위 N 묶음 로직은 DB와 분리한 순수 함수(`backend/analysis.py`)로 두어 단위 테스트한다.
- 프론트: 라인·설비 선택지는 기존 `GET /equipment`에서 만든다. 라인 선택 시 설비 목록은 그 라인 것만 보이고, 라인이 바뀌어 선택된 설비가 목록에 없으면 설비를 "전체"로 되돌린다.
- 하드코딩 금지: 기준일·신뢰도 등 화면 숫자는 전부 응답에서 온다. `mockDowntimeAnalysis.ts`는 삭제한다.

## AC

| # | Given | When | Then |
|---|---|---|---|
| AC-01 | 조건 없이 | `GET /downtime/analysis` | 200, `date_to`=오늘(KST), `date_from`=6일 전 |
| AC-02 | 기간 내 원인 3개(시간 60/30/10분) | 집계 | percent가 60.0/30.0/10.0, breakdown 3개, "기타" 없음 |
| AC-03 | 기간 내 원인 6개 | 집계 | breakdown은 상위 4 + "기타" 5개이고 percent 합계 100 ±0.1 |
| AC-04 | `downtime_min`이 0 이하인 종료 행 | 집계 | 시간·건수에서 제외, `needs_review_count`에 포함 |
| AC-05 | 사전에 없는 에러코드 행 | 집계 | label이 `"{코드} (사전 미등록)"`, `needs_review_count`에 포함 |
| AC-06 | `date_to`가 내일 | 조회 | 응답 `date_to`는 오늘 |
| AC-07 | `date_from` > `date_to` | 조회 | 422 |
| AC-08 | 해당 조건 기록 0건 | 조회 | 200, `event_count`=0, `top_equipment`=null, `causes`=[] |
| AC-09 | 화면 진입 | 필터를 라인 "LINE-A"로 변경 | 응답이 바뀌고 표에 다른 라인 설비는 나오지 않는다 |
| AC-10 | 조회 실패 후 | 다른 조건으로 변경 | 오류 카드가 사라지고 새 결과를 표시 |
| AC-11 | 화면 전체 | 소스 확인 | 화면에 "87%", "2026.09.18", `mockDowntimeAnalysis` 참조가 없다 |
