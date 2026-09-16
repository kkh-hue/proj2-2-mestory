# mcp_server — 진행상황

## 상태

- [ ]  도구 설계 — 무엇으로 나눌지 결정 (tool_description만 보고 구분 가능하게)
- [ ]  도구 4종 구현 (`example_tool` 대체)
  - [ ]  정지 로그 조회
  - [ ]  에러코드 사전 조회
  - [ ]  정비이력 조회
  - [ ]  (4번째 도구)
- [ ]  `skills/SKILL.md`의 판단 기준과 정합성 확인 (MCP 조회 결과 없이 규칙만으로 답하지 않기)
- [ ]  Claude Desktop / Cursor 또는 langchain-mcp-adapters로 연결 확인 (도구 호출 스크린샷)

## 실행 방법

```bash
python mcp_server/server.py
```

## TODO / 막힌 것

(진행하면서 여기에 채워주세요)
