# 리포트 API 연결 — CORS + 브라우저 직접 호출

## Why

- **페르소나**: 설비 정지 원인 리포트를 조회하는 사용자와 프론트엔드 개발자.
- **상황**: Next.js와 FastAPI가 서로 다른 Origin에서 실행된다.
- **문제**: Backend CORS 설정과 프론트 호출 함수가 없어 브라우저에서 리포트를 요청할 수 없다.
- **측정 지표**: 아래 AC 통과율, 기존 요청/응답 계약 변경 건수.

## Goal

- **성공 기준**: AC 8개 모두 통과, 기존 API 계약 변경 0건, 자동 재시도 0회.
- **Out of Scope**: UI 연결, 프록시, 인증, 세션 생성/저장, Railway 실제 설정 변경, 패키지 설치, 기존 Spec 변경.

## What

**Happy Path**
1. 호출자가 기존 ReportRequest를 createReport에 전달한다.
2. 브라우저가 허용된 Origin에서 JSON POST /report를 요청한다.
3. Backend가 기존 리포트 생성 흐름을 실행한다.
4. 호출 함수가 기존 DowntimeReport JSON을 반환한다.

**Edge Cases**

| 상황 | 처리 |
|---|---|
| CORS 변수 미설정 | http://localhost:3000 허용 |
| CORS 변수에 공백/빈 항목 포함 | 각 항목을 trim하고 빈 항목 제거; 명시적 빈 값은 허용 Origin 없음 |
| 미허용 Origin 또는 메서드 | 사전 요청 거부, 해당 Origin 허용 헤더 없음 |
| 운영 API URL 누락 | 요청 전 설정 오류 |
| HTTP 오류 | 상태 코드와 JSON 또는 텍스트 응답을 ReportApiError에 보존 |
| 네트워크 오류/취소 | 원래 오류 전달, 재시도 없음 |
| session_id 생략/null | 기존 Backend 기본값 유지 |

## How

- backend/main.py에 CORSMiddleware를 등록한다. CORS_ALLOWED_ORIGINS는 쉼표 구분 목록이며 미설정 기본값은 http://localhost:3000이다.
- allow_methods=["POST"], allow_headers=["Content-Type"], allow_credentials=False. OPTIONS는 미들웨어가 처리한다.
- frontend/lib/api.ts는 기존 ReportRequest, DowntimeReport 타입을 가져온다.
- createReport(request, options?: { signal?: AbortSignal }): Promise<DowntimeReport>를 제공한다.
- NEXT_PUBLIC_API_BASE_URL 끝의 슬래시를 제거하고 /report를 붙인다. 미설정/빈 값은 개발 시 localhost:8000, production에서는 오류다.
- Content-Type: application/json, JSON.stringify(request), 자동 재시도 없음. 응답 런타임 스키마 검증은 추가하지 않는다.
- ReportApiError는 status와 body를 제공한다. 네트워크 오류, 취소, 성공 응답 JSON 파싱 실패는 그대로 전달한다.
- 요청: line_id, equipment_id, date_from, date_to, session_id는 기존대로 선택적 문자열/null.
- 응답: equipment_id, line_id, period, causes, unclassified_count, confidence_note, recommended_action을 변경 없이 반환한다.
- 환경변수 예시에 로컬과 Railway 공개 URL을 설명한다. 실제 환경 파일/배포 설정은 변경하지 않는다.
- Backend 테스트는 기존 pytest/no_data 마커를 사용하고 generate_report를 모의 처리한다. 프론트는 기존 사용 가능한 도구로 타입 검사와 일회성 모의 fetch 검증을 한다.

## AC (Given-When-Then)

**AC-01** GIVEN CORS 변수 미설정 WHEN localhost:3000에서 POST/Content-Type 사전 요청 THEN 200과 정확한 허용 Origin 반환.

**AC-02** GIVEN 공백/빈 항목을 포함한 Origin 목록 WHEN 등록된 각 Origin이 사전 요청 THEN 각각 허용; localhost 자동 추가 없음.

**AC-03** GIVEN 미허용 Origin 또는 메서드 WHEN 사전 요청 THEN 400; 미허용 Origin에 Allow-Origin 헤더 없음. 명시적 빈 설정도 Origin을 허용하지 않음.

**AC-04** GIVEN 모의 리포트 생성기 WHEN 기존 전체 필드 또는 생략/null 필드로 POST THEN 인자가 그대로 전달되고 200과 기존 응답 JSON 반환. 허용 Origin 응답에는 CORS 헤더 포함.

**AC-05** GIVEN 잘못된 요청 필드 타입 WHEN POST THEN 기존 422 응답, 리포트 생성 호출 없음.

**AC-06** GIVEN API URL과 요청 WHEN createReport 호출 THEN 올바른 URL/POST/JSON 헤더/본문으로 1회 요청하고 응답 JSON 반환. 개발 URL 기본값과 운영 URL 누락 오류도 확인.

**AC-07** GIVEN JSON 또는 텍스트 HTTP 오류 WHEN createReport 호출 THEN ReportApiError에 상태/본문 보존, 재시도 없음.

**AC-08** GIVEN 네트워크 오류 또는 취소 WHEN createReport 호출 THEN 같은 오류 전달, signal 전달, 재시도 없음.
