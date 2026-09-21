# Spec — 멀티모달 입력 (이미지 첨부 원인 분석)

- 담당: 박민영 · 상태: **검증 완료, 구현 대기 (팀 합의 필요)**
- 코드: `backend/services/llm.py`, `backend/main.py`, `frontend/components/ChatInput.tsx`, `frontend/lib/api.ts`, `frontend/types/report.ts`
- 근거: 2차 프로젝트 가이드 21쪽 가산점 — **멀티모달 확장 +5** (*"이미지·음성 등 텍스트 외 입력을 실제 기능으로 통합"*)
- ⚠️ `llm.py`·`main.py`는 홍민하 님 파일, `frontend/`는 강경희 님 파일 → **이 Spec으로 합의 후 구현**

## Why

- **페르소나**: 현장 설비 엔지니어·생산관리자. 그 요청을 받는 것은 리포트를 만드는 LangChain 에이전트(LLM).
- **상황**: 설비가 멈췄고 HMI 패널에 알람이 떠 있다. 엔지니어는 그 화면을 휴대폰으로 찍는다. 또는 파손된 부품을 찍는다.
- **문제**:
  1. 현재는 **설비ID·에러코드·기간을 손으로 입력**해야 리포트가 나온다. 화면에 다 적혀 있는데도 다시 타이핑해야 한다.
  2. 현장에서 **눈으로 본 것**(화면에 뜬 경고 문구, 베어링 마모, 누유 흔적)이 리포트 근거에 전혀 들어가지 않는다. 텍스트 조건만으로는 전달할 방법이 없다.
  3. 정지 원인이 데이터에 안 남는 경우가 많다 — `ETC-604`(원인 미확인)가 **641건**, 빈 코드·미등록 코드도 있다. 이럴 때 이미지가 유일한 추가 근거다.
- **측정 지표**:
  - 이미지 속 설비ID·에러코드를 `visual_findings`에 정확히 담은 비율 (**추출 정확도**)
  - 같은 평가셋에서 **이미지를 제거했을 때 점수 하락폭** (= 이미지가 실제로 기여했다는 증거)

## Goal

- **해결 목표**: 질문에 이미지를 첨부하면, LLM이 **텍스트 조건 + 이미지 + MCP 조회 결과**를 함께 근거로 리포트를 만든다. 그리고 **이미지가 실제로 쓰였는지를 출력에서 확인할 수 있다.**
- **성공 기준 (숫자)**
  - S-1. 이미지에 적힌 설비ID·에러코드가 `visual_findings`에 담긴다 — 평가셋 기준 **추출 정확도 측정 가능**
  - S-2. 이미지를 넣으면 `used_image=true`, 빼면 `false` — **100% 정확**
  - S-3. **이미지 없는 기존 요청은 동작이 바뀌지 않는다** (회귀 0건, 기존 pytest 전건 통과)
  - S-4. 이미지 포함 요청 **최악1건 ≤ 28초** / 텍스트 전용 **최악1건 ≤ 24초** (게이트 2줄)

    > ⚠️ **2026-09-21에 목표치를 바꿨다.** 옛 목표는 `p95 ≤ 20초` / `10초`였다.
    > 그 숫자는 gpt-4o-mini 시절에 만든 것인데, 그 모델은 ZDR 조건에서 tool calling
    > 엔드포인트가 0개가 되어 쓸 수 없다. 추론 모델로 갈아탄 뒤로 **두 줄 다 한 번도
    > 지키지 못했다.** 실측 범위에 여유를 더해 다시 잡은 값이며, **성능이 좋아져서가
    > 아니라 기준을 낮춘 것**이다.
    >
    > 또한 `score_multimodal.py`가 `p95`로 부르던 값은 케이스 10건에서는 **사실상
    > 가장 느린 1건**이다(`int(10*0.95)=9` → 정렬한 10개 중 마지막). 그래서 지표 이름을
    > `최악1건`으로 고쳤다. 회차별 수치·근거·한계는 **`evals/EVAL_REPORT.md`** 참고.
  - S-5. 잘못된 이미지 입력(형식 오류·용량 초과)에 서버가 죽지 않고 안내를 돌려준다
- **Out of Scope**
  - **음성·동영상 입력** (이미지만)
  - **이미지에서 조건을 추출해 자동으로 조회 조건을 채우는 것** — 이미지는 *보조 근거*로만 쓴다. 설비ID·기간은 사용자 입력이 정답이다 (실행계획 D-5)
  - OCR 라이브러리 도입 (LLM의 vision 능력만 사용)
  - 이미지 저장·이력 관리 (요청 1회에만 쓰고 버린다)
  - 파인튜닝 (실행계획 D-2, 보류)
  - `severity` 타입의 프론트 불일치 수정 (별건 — `types/report.ts`에 `"판정 불가"` 누락)

## What

**Happy Path**

1. 사용자가 프론트에서 기간·라인·설비를 입력하고, **이미지 파일을 1장 첨부**한다.
2. 프론트가 이미지를 **data URL(base64)** 로 바꿔 `ReportRequest.images` 배열에 담아 `POST /api/agent`(또는 `/report`)로 보낸다.
3. 라우터(`main.py`)는 검증만 하고 `generate_report(images=...)`로 **그대로 전달**한다.
4. `generate_report`가 `HumanMessage(content=[{text}, {image_url}, ...])`를 만든다.
5. 에이전트가 이미지를 보고 **MCP 도구 3개를 골라 호출**한다 (기존과 동일).
6. LLM이 출력 계약에 맞춰 JSON을 낸다. 이때 **이미지에서 읽어낸 것은 `visual_findings`에 따로 적고**, `used_image=true`로 표시한다.
7. 검증·3단계 폴백은 **기존 로직을 그대로 재사용**한다.

**이미지를 안 넣은 경우**
- `images`가 없거나 빈 배열이면 `HumanMessage(content="문자열")` — **기존과 완전히 동일한 경로**. `visual_findings=null`, `used_image=false`.

**합계·기록 규칙**

| 항목 | 규칙 |
|---|---|
| 대화 기록(`_SESSION_STORE`) | **이미지 base64를 저장하지 않는다.** 텍스트 부분만 저장 |
| Langfuse 트레이스 | base64를 **마스킹**해서 보낸다 (`data:image/png;base64,<39286자 생략>` 형태) |
| `equipment_id`/`line_id`/`period` | 기존대로 **사용자 입력이 정답** — LLM 출력으로 덮어쓰지 않는다. 단 `line_id`는 설비ID가 주어지면 `resolve_scope()`(`backend/scope.py`)가 설비 마스터에서 채운다 — LLM 출력이 아니라 마스터 조회이므로 이 원칙에 어긋나지 않는다 |
| `visual_findings` | LLM이 이미지에서 읽은 사실만. 추론·판정은 `causes`에 |

**Edge Cases**

| # | 상황 | 처리 방식 |
|---|---|---|
| EC-01 | `images` 없음 / 빈 배열 | 기존 텍스트 경로. `used_image=false`, `visual_findings=null` |
| EC-02 | data URL 형식이 아님 | `ValueError` → HTTP 422 (FastAPI 검증). 서버는 계속 동작 |
| EC-03 | 지원하지 않는 형식 (png·jpeg·webp 외) | 422 + 지원 형식 안내 |
| EC-04 | 이미지 용량 초과 (1장 5MB, 합계 10MB) | 422 + 용량 안내. **이유: base64는 원본보다 약 33% 커지고, 큰 이미지는 p95 게이트를 깬다** |
| EC-05 | 이미지 장수 초과 (최대 3장) | 422 + 장수 안내 |
| EC-06 | 이미지에 설비ID·에러코드가 안 보임 (흐림·기울임·저해상도) | `visual_findings`에 **읽어낸 것만** 적고, 못 읽었으면 빈 배열. **추측해서 채우지 않는다.** `confidence_note`에 "이미지에서 식별 불가" 명시 |
| EC-07 | 이미지 속 설비ID가 사용자 입력과 다름 | **사용자 입력을 따른다.** 불일치를 `confidence_note`에 적는다 (사람 확인 필요) |
| EC-08 | 이미지가 설비와 무관 (풍경·인물 등) | `visual_findings`에 "요청과 무관한 이미지" 1건. 원인 판정은 텍스트·MCP 근거로만 |
| EC-09 | 이미지가 있는데 LLM이 `visual_findings`를 비워 보냄 | 1차 검증 실패 → 기존 재시도 경로. 3차까지 실패하면 기존 안전 응답 |
| EC-10 | 이미지 때문에 토큰 한도 초과 | 모델 오류 → 기존 폴백. `confidence_note`에 안내 |

## How

```
API: POST /api/agent   (신규 — 가이드 6쪽 공통 포맷)
     POST /report      (기존 경로 유지, 같은 핸들러)

요청 (ReportRequest):
  line_id       : str | None   예 "LINE-A"          (기존)
  equipment_id  : str | None   예 "EQ-001"          (기존)
  date_from     : str | None   "YYYY-MM-DD"        (기존)
  date_to       : str | None   "YYYY-MM-DD"        (기존)
  session_id    : str | None                        (기존)
  images        : list[str] | None   ← 신규
      - data URL 형식: "data:image/png;base64,..."
      - 허용 형식: png, jpeg, webp
      - 최대 3장, 1장 5MB, 합계 10MB

출력 (DowntimeReport):
  equipment_id, line_id, period, causes[], unclassified_count,
  confidence_note, recommended_action                (기존)
  visual_findings : list[str] | None   ← 신규
      - 이미지에서 읽어낸 사실만. 예:
        ["화면에 에러코드 M-204 표시됨",
         "설비 태그 EQ-001 확인",
         "타임스탬프 2026-08-10 22:14:03"]
      - 이미지 없으면 null
  used_image      : bool               ← 신규

입력 오류: HTTP 422 (FastAPI 기본) + 한국어 detail
```

**프롬프트 구성 — 여기가 이 기능의 핵심이다**

```python
# 현재 (llm.py:188) — 이미지가 조용히 사라진다
("human", "{input}")

# 변경 후
MessagesPlaceholder("input")

# 호출 시
await executor.ainvoke({
    "input": [HumanMessage(content=[
        {"type": "text", "text": user_input},
        {"type": "image_url", "image_url": {"url": data_url}},   # 이미지 있을 때만
    ])],
    "chat_history": chat_history,
})
```

**왜 `("human","{input}")`을 쓰면 안 되는가 (9/18 검증으로 확인)**
`ChatPromptTemplate`의 `("human", "...")`은 **문자열 f-string 템플릿**이다. 여기에 리스트를 넣으면 리스트가 `str()`로 변환돼 `"[{'type': 'text', ...}]"` 같은 **글자**가 된다. **에러가 나지 않는다** — 이미지가 사라진 채로 그냥 동작한다. `MessagesPlaceholder`는 메시지 객체를 그대로 통과시키므로 `content`가 리스트로 유지된다.

**부수 효과**: `MessagesPlaceholder`는 템플릿 해석을 하지 않으므로, 사용자 입력에 대해서는 `_escape_braces`(llm.py:166)가 **불필요해진다**. 시스템 프롬프트(SKILL.md·스키마)에는 계속 필요하다.

**모델 선택 (실측 근거)**

| 설정 | 이미지 토큰 | 이미지 1장 비용 |
|---|---|---|
| gpt-4o-mini (현재) | 25,530 | $0.00383 |
| gpt-4o | ~765 | **$0.00191** |
| gpt-4o-mini + `detail:low` | 2,833 | $0.00043 |
| gpt-4o + `detail:low` | 85 | $0.00021 |

gpt-4o-mini는 이미지를 gpt-4o보다 **17~33배 많은 토큰**으로 계산한다. 텍스트 단가는 1/17이지만 이미지에서는 상쇄되고도 남아 **이미지에 관해서는 gpt-4o가 더 싸다.**
→ **모델 라우팅으로 분리한다** (별건, `MESTORY_LLM_MODEL_VISION` 환경변수):
- 이미지 없는 요청 → `openai/gpt-4o-mini`
- 이미지 있는 요청 → `openai/gpt-4o`

*(OpenRouter 2026-09 기준: gpt-4o-mini $0.15/M in, gpt-4o $2.50/M in)*

**제약**
- `_SESSION_STORE`(llm.py:117)에 base64를 넣으면 **다음 요청마다 통째로 재전송**된다 → 텍스트만 저장
- Langfuse 트레이스에 base64(샘플 39,286자)가 그대로 찍히면 트레이스를 읽을 수 없다 → 마스킹
- MCP 도구(`mcp_server/`)는 **변경 없음**
- stdio 방식이므로 `print()` 금지 (기존과 동일)
- 프론트 `types/report.ts`는 백엔드 계약과 **같이** 고쳐야 한다 (파일 맨 위 주석 참고)

**평가용 이미지**
실제 공장 HMI 사진이 없고, 인터넷 사진은 적힌 설비ID가 우리 데이터와 무관해 조회가 안 된다.
→ `scripts/make_hmi_images.py`로 **우리 데이터를 박은 HMI 알람 화면을 생성**한다. 정답을 처음부터 알고 있으므로 채점이 명확하다. 저해상도·기울임·흐림 버전도 같은 스크립트로 만들어 실패 유도 케이스로 쓴다.

## AC (Given-When-Then)

**AC-01 · 이미지가 프롬프트를 통과한다**
- GIVEN: `MessagesPlaceholder("input")`을 쓴 프롬프트
- WHEN: `{"input": [HumanMessage(content=[{text}, {image_url}])]}`로 렌더링
- THEN: human 메시지의 `content`가 **`list` 타입**이고, `type == "image_url"`인 항목이 있다

**AC-02 · 현재 코드로는 이미지가 사라진다 (회귀 방지용 반례)**
- GIVEN: `("human", "{input}")`을 쓴 프롬프트
- WHEN: 같은 리스트로 렌더링
- THEN: human 메시지의 `content`가 **`str` 타입**이다 (= 이미지 소실)

**AC-03 · 에이전트 파이프라인 끝까지 이미지가 남는다**
- GIVEN: `create_tool_calling_agent` + `AgentExecutor` + `MessagesPlaceholder("input")`
- WHEN: 이미지가 담긴 입력으로 `invoke`
- THEN: 에이전트 생성이 성공하고, 모델이 받은 human 메시지의 `content`가 `list`이며 이미지 항목이 있다

**AC-04 · 이미지 없는 요청 회귀 없음**
- GIVEN: 변경된 `_build_prompt`
- WHEN: `images` 없이 `line_id="LINE-A", date_from="2026-08-10", date_to="2026-08-10"`으로 요청
- THEN: 기존과 같은 리포트가 나오고, `used_image` false, `visual_findings` null. **기존 pytest 전건 통과**

**AC-05 · 이미지가 근거에 반영된다**
- GIVEN: `EQ-001` / `M-204` / `2026-08-10 22:14:03`이 적힌 HMI 화면 이미지
- WHEN: 그 이미지를 첨부해 요청
- THEN: `used_image` true, `visual_findings`에 **"M-204"와 "EQ-001"이 각각 포함된 항목**이 있다

**AC-06 · 이미지를 빼면 달라진다 (기여 증명)**
- GIVEN: AC-05와 **완전히 같은 텍스트 조건**
- WHEN: 이미지만 제거하고 요청
- THEN: `used_image` false, `visual_findings` null. **같은 평가셋으로 두 번 측정한 점수 차이를 EVAL_REPORT에 기록**

**AC-07 · 읽을 수 없는 이미지는 추측하지 않는다**
- GIVEN: 같은 화면을 흐리게·저해상도로 만든 이미지
- WHEN: 첨부해 요청
- THEN: `visual_findings`가 빈 배열이거나 읽어낸 항목만 있고, **데이터에 없는 코드를 지어내지 않는다.** `confidence_note`에 식별 불가 언급

**AC-08 · 이미지 속 설비ID가 입력과 다를 때**
- GIVEN: `EQ-001`이 적힌 이미지
- WHEN: `equipment_id="EQ-010"`으로 함께 요청
- THEN: `report.equipment_id`는 **"EQ-010"**(사용자 입력), `confidence_note`에 불일치 언급

**AC-09 · 잘못된 이미지 입력**
- WHEN: `images=["not-a-data-url"]` / 지원 외 형식 / 5MB 초과 / 4장
- THEN: HTTP **422**와 한국어 detail. **서버는 계속 동작한다**

**AC-10 · base64가 기록에 남지 않는다**
- GIVEN: `session_id`를 준 이미지 요청
- WHEN: 같은 `session_id`로 두 번째 요청
- THEN: `_SESSION_STORE`의 기록에 `"data:image"` 문자열이 **없다**. Langfuse로 보내는 입력에도 원본 base64가 없다

**AC-11 · `/api/agent` 경로**
- WHEN: `POST /api/agent`로 AC-04와 같은 본문 전송
- THEN: `POST /report`와 **같은 응답**. 두 경로 모두 200
