# 분석 리포트 PDF 저장

## Why

- **페르소나**: 설비 다운타임 분석 결과를 현장 공유 또는 보관해야 하는 생산 관리자
- **상황**: 화면에서 확인한 분석 결과를 별도 파일로 저장해야 한다.
- **문제**: 현재 결과는 브라우저 화면에서만 확인할 수 있다.
- **측정 지표**: 분석 완료 후 사용자가 결과를 브라우저의 PDF 저장 기능으로 보관할 수 있다.

## Goal

- 현재 `DowntimeReport` 응답만으로 인쇄 가능한 리포트를 생성한다.
- 기존 분석 결과를 그대로 사용하며 LLM, MCP, Backend API를 다시 호출하지 않는다.
- **Out of Scope**: 기존 결과 화면에 버튼 연결, PDF 서버 생성, KPI/TOP3 포함, PDF 파일 서버 보관.

## What

**Happy Path**

1. 독립 `PdfDownloadButton`이 `DowntimeReport`를 props로 받는다.
2. 사용자가 버튼을 누르면 별도 인쇄용 문서가 열린다.
3. 문서에는 조회 조건, 원인 목록, 권장 조치, 참고 사항, 데이터 확인 건수가 표시된다.
4. 사용자는 브라우저 인쇄 대화상자에서 PDF로 저장한다.

**Edge Cases**

| 상황 | 처리 |
| --- | --- |
| 원인이 없음 | “분석된 원인이 없습니다.”를 표시한다. |
| evidence가 비어 있음 | “제공된 판단 근거가 없습니다.”를 표시한다. |
| 긴 설명 또는 근거 | 줄바꿈과 단어 분리 CSS를 적용한다. |
| 팝업 차단 | 버튼 아래 오류 메시지로 팝업 허용을 안내한다. |
| 한글 표시 | 브라우저/OS의 한글 지원 산세리프 폰트 우선순위를 사용한다. |

## How

- 입력 타입: 기존 `frontend/types/report.ts`의 `DowntimeReport`
- 출력: 별도 브라우저 인쇄 문서 및 `window.print()` 호출
- 데이터: `period`, `line_id`, `equipment_id`, `causes`, `recommended_action`, `confidence_note`, `unclassified_count`만 사용
- 보안: 텍스트를 HTML escape하여 문서에 삽입한다.
- 제약: 기존 파일을 수정하거나 기존 화면에 연결하지 않는다.

## AC (Given-When-Then)

- GIVEN 분석 결과에 원인이 존재할 때, WHEN PDF 버튼을 누르면, THEN 각 원인의 코드·설명·심각도·확정 상태·근거가 인쇄 문서에 표시된다.
- GIVEN `causes`가 비어 있을 때, WHEN PDF 버튼을 누르면, THEN 빈 상태 문구가 표시되고 오류 없이 인쇄 대화상자가 열린다.
- GIVEN evidence가 비어 있을 때, WHEN PDF 버튼을 누르면, THEN 대체 문구가 표시된다.
- GIVEN 기존 분석 결과가 있을 때, WHEN PDF 버튼을 누르면, THEN LLM, MCP, `/report` API 호출은 추가로 발생하지 않는다.
