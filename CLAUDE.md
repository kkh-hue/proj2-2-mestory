# CLAUDE.md

이 프로젝트의 AI 에이전트 공통 지침은 [AGENTS.md](./AGENTS.md)를 따릅니다 (Claude Code·Codex 등 도구 무관 공통 문서). 프로젝트 개요·폴더 구조·도메인 규칙·협업 규칙은 모두 그쪽에 있습니다.

@AGENTS.md

---

아래는 **Claude Code로 이 저장소를 다룰 때만** 필요한 내용입니다.

## 줄바꿈(CRLF) — 여기서 가장 자주 사고가 난다

git HEAD는 LF, 작업 폴더는 CRLF다(`core.autocrlf=true`, `.gitattributes` 없음).

- 파일을 저장만 해도 수정된 것처럼 보인다 → **`git add .` 대신 파일명을 지정**한다.
- 편집 도구가 줄바꿈을 바꾸면 diff가 파일 전체로 부풀어 리뷰가 불가능해진다. 편집 후 `git diff --stat`으로 **변경 줄 수가 예상과 맞는지** 확인한다.
- `git diff --ignore-all-space --stat`가 비어 있으면 실제 변경은 없다.

## 테스트

```powershell
.venv\Scripts\python.exe -m pytest -q
```

`AGENTS.md`의 완료 기준대로, **테스트를 돌리기 전에는 "완료"라고 보고하지 않는다.** 데이터가 없으면 일부 skip 되는 것이 정상이다.

## MCP 서버를 고칠 때

- **stdio 방식이므로 `print()` 금지.** 표준출력이 프로토콜 채널이라 한 줄만 찍어도 연결이 깨진다. 로그는 `logger`로 남긴다.
- `mcp_server/tools/`(순수 조회 함수)와 `mcp_server/server.py`(MCP 포장)의 **분리를 유지**한다. 도구 함수는 MCP를 몰라야 테스트가 쉽다.

## 백엔드를 고칠 때

- `backend/services/llm.py`·`backend/main.py`는 홍민하 님, `frontend/`는 강경희 님 파일이다. 직접 고칠 때는 **Spec으로 합의를 구하는 방식**으로 진행하고 PR 설명에 밝힌다.
- 프론트 `types/report.ts`는 백엔드 출력 계약과 **같이** 고친다. 한쪽만 고치면 타입이 조용히 어긋난다(실제로 `판정 불가` 누락으로 배지가 색 없이 렌더링된 적 있다).

## 개인 작업 규칙

개인용 지침은 `CLAUDE.local.md`에 둔다. `.gitignore` 대상이라 저장소에 올라가지 않는다.
