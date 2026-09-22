# 추가 기능 UI 미리보기

## Why

- **페르소나**: 신규 기능의 화면 구성만 빠르게 확인하려는 팀원
- **상황**: KPI, PDF, 로그인, 히스토리는 기존 분석 화면에 아직 연결하지 않았다.
- **문제**: 독립 컴포넌트의 시각적 구성을 실제 브라우저에서 함께 확인하기 어렵다.
- **측정 지표**: `/preview-features`에서 다섯 컴포넌트가 API 호출 없이 렌더링된다.

## Goal

- 신규 기능 UI 전용 route를 제공한다.
- **Out of Scope**: 기존 route 수정, 실제 API/DB/인증/PDF 분석 결과 연결, 기능 배포 확정.

## What

1. route 내부의 명시적 PREVIEW 샘플 데이터를 각 컴포넌트 props로 전달한다.
2. UI 상단에 실제 데이터가 아닌 미리보기임을 표시한다.
3. 로그인은 미연결 상태, 히스토리는 PREVIEW 항목만 표시한다.

## How

- 신규 route 파일만 사용한다.
- 샘플 데이터는 `frontend/app/preview-features/page.tsx`에만 둔다.
- 기존 `DowntimeReport` 및 컴포넌트 prop 타입을 사용한다.

## AC (Given-When-Then)

- GIVEN `/preview-features`에 접속할 때, WHEN 페이지가 렌더링되면, THEN API 호출 없이 다섯 UI 컴포넌트가 표시된다.
- GIVEN 미리보기 데이터가 있을 때, WHEN 화면을 보면, THEN PREVIEW 전용 데이터임이 명확히 표시된다.
