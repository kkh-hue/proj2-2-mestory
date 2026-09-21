# Spec — 채팅 첨부 사진 유지 (새로고침 후에도 보이게)

- 담당: 박민영 · 상태: 작성 완료, 구현 대기
- 코드: `backend/db.py`, `backend/images.py`(신규), `backend/services/llm.py`,
  `backend/requirements.txt`, `frontend/types/report.ts`, `frontend/app/downtime/ai/page.tsx`
- 앞선 Spec: [multimodal.md](./multimodal.md) — AC-10의 취지를 좁혀서 다시 정의한다
- ⚠️ `llm.py`는 홍민하 님, `frontend/`는 강경희 님 영역 → PR 설명에 밝힌다

## Why

- **페르소나**: 현장 설비 엔지니어. HMI 화면을 찍어 첨부하고 원인을 묻는다.
- **상황**: 사진을 보내고 답을 받은 뒤, 나중에 같은 세션을 다시 연다.
- **문제**:
  1. 새로고침하면 **내가 올린 사진이 사라진다.** 답변의 "이미지에서 확인한 것"은 남는데
     정작 근거가 된 사진이 없어, 그 분석이 무엇을 보고 나온 것인지 확인할 수 없다.
  2. 세션 목록에서 과거 대화를 열면 사진 없는 반쪽 기록만 남는다.
- **측정 지표**: 새로고침 후 사용자 말풍선에 사진이 보이는지(수동 확인),
  그리고 턴당 저장 용량(썸네일 적용 전후 비교).

## Goal

- **해결 목표**: 첨부한 사진을 **화면 표시 전용으로** 저장해, 새로고침·세션 재진입 후에도
  사용자 말풍선에 보이게 한다.
- **성공 기준**
  1. 새로고침 후 사용자 말풍선에 첨부 사진이 보인다.
  2. **`load_chat_history()` 결과에 `"data:image"` 문자열이 없다** — AC-10의 핵심은 유지한다.
  3. 저장되는 이미지 1장이 **200KB 이하**(base64 기준)로 줄어든다.
  4. 기존 호출부 변경 없이 회귀가 없다.
- **Out of Scope**
  - 이미지 저장소(S3·볼륨) 도입 — DB 컬럼에 담는다.
  - 이미지 편집·회전·다시 보내기.
  - assistant 턴에 이미지 붙이기 — 사용자가 올린 사진만 다룬다.
  - 과거에 저장된 대화의 사진 복원 — 저장 안 했으므로 불가능하다.
  - **LLM에 보내는 이미지를 줄이는 것** — vision 정확도에 영향을 주므로 원본 그대로 보낸다.

## What

### AC-10을 다시 읽는다 (취지를 좁힌다)

`multimodal.md` AC-10은 *"base64가 기록에 남지 않는다"*였고, 실제 시험은
`_build_user_messages()`의 `history_text`만 검사한다. 원래 막으려던 것은
**"이미지가 LLM 대화 맥락에 들어가 후속 질문마다 재전송되는 것"**이지,
화면에 다시 그리는 것까지 막으려던 게 아니다.

이 Spec은 그 경계를 코드로 분명히 한다.

| 칸 | 읽는 함수 | 쓰이는 곳 | 이미지 |
|---|---|---|---|
| `content` | `load_chat_history()` | LLM 프롬프트 | ❌ **절대 금지** |
| `display_content` | `list_chat_turns()` | 화면 말풍선(글) | — |
| **`display_images`** (신규) | `list_chat_turns()` | 화면 말풍선(사진) | ✅ 여기만 |

`display_content`가 이미 쓰고 있는 패턴을 그대로 따른다.

### 왜 원본이 아니라 썸네일인가

측정값이다. 백엔드 상한은 1장 5MB인데, base64는 약 1.33배가 된다.

| 사진 | base64 | 3장 |
|---|---|---|
| 평가용 PNG (35~80KB) | 46~106KB | ~300KB |
| 휴대폰 사진 1MB | 1.3MB | 4.0MB |
| 휴대폰 사진 5MB (상한) | 6.7MB | **20MB** |

`list_chat_turns()`는 **세션의 모든 턴을 한 번에** 돌려준다. 사진 3장짜리 턴이 5번이면
응답이 100MB가 되어 세션 로딩이 사실상 멈춘다.

말풍선에 보이는 건 작은 썸네일이므로 원본 해상도가 필요 없다.
**LLM에는 원본을, DB에는 썸네일을** 보낸다 — 분석 정확도는 그대로 두고 저장만 줄인다.

**Happy Path**
1. 사용자가 사진을 첨부해 질문한다.
2. `generate_report`가 **원본 이미지를 LLM에 보낸다** (지금과 동일).
3. user 메시지를 저장할 때 `images=원본`을 함께 넘긴다.
4. `save_message`가 **썸네일로 줄여** `display_images` 칸에만 담는다. `content`는 텍스트만.
5. 새로고침 → `list_chat_turns()`가 `images`를 함께 돌려준다.
6. 화면이 `turn.images`를 그린다 (**이미 구현돼 있다** — 값만 연결하면 된다).

**Edge Cases**

| # | 상황 | 처리 |
|---|---|---|
| EC-01 | 이미지 없는 요청 | `display_images`가 NULL. 기존과 동일 |
| EC-02 | 이 기능 이전에 저장된 대화 | NULL → 사진 없이 그린다. 에러 없음 |
| EC-03 | 썸네일 변환 실패(깨진 파일 등) | **그 이미지만 건너뛰고 로그를 남긴다.** 리포트 생성은 계속한다 |
| EC-04 | 투명 PNG | JPEG는 알파를 못 담으므로 흰 배경에 합성 |
| EC-05 | 원본이 이미 썸네일보다 작음 | 확대하지 않는다. 그대로 쓴다 |
| EC-06 | assistant 턴 | 이미지를 넣지 않는다 |
| EC-07 | DB 저장 실패 | 기존 `save_message`의 예외 경로 그대로 |

## How

```
# 스키마 (이미 배포된 테이블이라 alter 방식 — display_content와 같은 방법)
alter table chat_messages add column if not exists display_images jsonb

# backend/images.py (신규)
THUMBNAIL_MAX_PX = 512      # 가로·세로 중 긴 쪽 기준, 비율 유지
THUMBNAIL_QUALITY = 70      # JPEG 품질
to_thumbnail(data_url: str) -> str | None       # 실패하면 None
to_thumbnails(data_urls: list[str]) -> list[str]  # None인 것은 빼고 돌려준다

# backend/db.py
save_message(session_id, role, content, report_id=None,
             display_content=None, images=None)   # images 인자 추가 (기본 None = 회귀 없음)
list_chat_turns() -> turn["images"] = display_images   # 값이 있을 때만 키를 넣는다
load_chat_history()                                     # 손대지 않는다

# backend/services/llm.py
await save_message(session_id, "user", history_text,
                   display_content=user_display, images=images)   # 인자만 추가

# backend/requirements.txt
Pillow>=11.0    # 썸네일 변환용 (지금은 scripts/make_hmi_images.py만 써서 런타임 의존성에 없었다)

# frontend/types/report.ts
interface ChatTurn { ...; images?: string[] }   # ChatTurnView 로컬 타입에만 있던 것을 계약으로 올린다
```

- 컬럼 타입은 **`jsonb`** — 같은 파일의 `reports.causes`·`reports.visual_findings`가 이미 jsonb다.
  psycopg가 리스트를 직렬화/역직렬화해 주므로 `json.dumps`를 직접 쓰지 않는다.
- 썸네일 변환은 **저장 직전(`save_message`)에서** 한다. 호출부가 원본을 넘겨도
  DB에는 항상 줄어든 것만 들어가게 하여, 다른 곳에서 실수로 원본을 저장하는 길을 막는다.

## AC (Given-When-Then)

**AC-01 · 새로고침 후에도 사진이 보인다**
- GIVEN: 사진 1장을 첨부해 질문한 세션
- WHEN: 새로고침해 같은 세션을 연다
- THEN: 사용자 말풍선에 그 사진이 보인다 (수동 확인 — 프론트 테스트 러너가 없다)

**AC-02 · LLM 맥락에는 이미지가 들어가지 않는다 (AC-10 유지)**
- GIVEN: `display_images`에 이미지가 저장된 세션
- WHEN: `load_chat_history(session_id)`를 부른다
- THEN: 반환된 어떤 메시지의 `content`에도 `"data:image"`가 없다

**AC-03 · 저장되는 이미지가 충분히 작다**
- GIVEN: 1MB 이상인 이미지 data URL
- WHEN: `to_thumbnail()`을 거친다
- THEN: 결과가 **200KB 이하**이고, 여전히 `data:image/`로 시작하는 유효한 data URL이다

**AC-04 · 변환 실패가 리포트 생성을 막지 않는다**
- GIVEN: base64가 깨져 이미지로 열 수 없는 data URL
- WHEN: `to_thumbnails([깨진 것, 정상인 것])`을 부른다
- THEN: 예외를 올리지 않고 정상인 것만 담긴 목록을 돌려준다

**AC-05 · 이미지 없는 요청에 회귀가 없다**
- GIVEN: `images` 없이 기존 형태로 `save_message(...)`를 호출
- WHEN: `list_chat_turns()`로 읽는다
- THEN: 예외 없이 동작하고 `images` 키가 없다

**AC-06 · 옛 대화도 깨지지 않는다**
- GIVEN: `display_images`가 NULL인 행
- WHEN: `list_chat_turns()`로 읽는다
- THEN: 그 턴에 `images`가 없고 나머지 필드는 정상이다
