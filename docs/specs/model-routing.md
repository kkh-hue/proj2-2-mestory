# Spec — 이미지 유무에 따른 모델 라우팅

- 담당: 박민영 · 상태: **구현 완료 / 기능은 꺼둔 상태** (PR #92·#94 머지)
- 코드: `backend/services/llm.py`(`resolve_model_name`·`_build_llm`), `backend/main.py`(완료 로그),
  `scripts/score_multimodal.py`(회차 기록), `tests/test_model_routing.py`
- 근거: 2차 프로젝트 가이드 가산점 — **모델 라우팅 +3** (*"비용 절감 효과를 수치로 제시"*)
- **켜는 법**: `.env`에 `MESTORY_LLM_MODEL=openai/gpt-5-nano` +
  `MESTORY_LLM_MODEL_VISION=openai/gpt-5-mini`. **설정하기 전까지는 기존과 똑같이 동작한다.**
- ⚠️ **아직 켜지 않았다.** 텍스트 요청당 비용은 **−77%**(`$0.003495` → `$0.000803`)지만,
  최악1건 지연이 **41.8초**로 게이트(24초)를 넘는다. 원인은 모델 속도가 아니라 **재시도 2.0배**다.
  근거와 판단은 `evals/EVAL_REPORT.md` 7절.

## Why

- **페르소나**: 설비 담당자. 하루 대부분의 질문은 텍스트만으로 하고, 화면 사진은 가끔 첨부한다.
- **상황**: 지금은 이미지가 있든 없든 전부 `openai/gpt-5-mini` 하나로 처리한다.
- **문제**:
  1. 텍스트만 묻는 요청에도 vision 지원 모델의 단가를 그대로 낸다.
  2. gpt-5-mini는 ZDR 제약 때문에 고른 모델이지 비용 때문에 고른 모델이 아니다.
     (`openai/gpt-4o-mini`는 ZDR+tools 조합에서 404 — AGENTS.md "알려진 문제" 참고)
  3. OpenRouter 실측 지연 집계에서 gpt-5-mini는 p50 3,214ms / p90 9,458ms로
     ZDR 후보군 56개 중 가장 느린 축이다. 텍스트 요청까지 이 지연을 낼 이유가 없다.
- **측정 지표**: 텍스트 요청 1건당 LLM 비용, 텍스트 요청 p95 지연.

## Goal

- **해결 목표**: 이미지가 없는 요청은 `openai/gpt-5-nano`로, 이미지가 있는 요청은
  기존 `openai/gpt-5-mini`로 보낸다. 환경변수로 켜고 끌 수 있어야 한다.
- **성공 기준**
  1. `MESTORY_LLM_MODEL_VISION`이 없으면 **기존과 100% 동일하게 동작**한다(회귀 없음).
  2. 텍스트 요청의 입력·출력 단가가 각각 80% 낮아진다 (Azure 기준 $0.25/$2.00 → $0.05/$0.40).
  3. 라우팅 후에도 이미지 경로의 `contract`(스키마 준수) 축이 기존 gpt-5-mini 범위
     (0.975~1.000) 아래로 떨어지지 않고, 텍스트 경로의 지연이 게이트를 넘지 않는다.
  4. 요청당 비용 비교표(라우팅 전/후)를 실측 토큰으로 제시한다.
- **Out of Scope**
  - 텍스트 평가셋(`evals/dataset.jsonl` 30건) 전용 채점 스크립트 신규 작성.
    (현재 없음 — 품질 AC는 기존 `--no-image-control` 대조군으로 대신한다)
  - 3개 이상 모델로의 라우팅, 요청 난이도·길이 기반 라우팅.
  - `MESTORY_LLM_REASONING_EFFORT`의 모델별 분리. (지연 게이트 작업에서 따로 다룬다)
  - 폴백 시 다른 모델로 재시도하는 구조.

## What

**Happy Path**

1. 사용자가 이미지 없이 질문 → `generate_report(images=None)`
2. `resolve_model_name(has_images=False)` → `MESTORY_LLM_MODEL`(= gpt-5-nano) 반환
3. 사용자가 화면 사진을 첨부 → `generate_report(images=[...])`
4. `resolve_model_name(has_images=True)` → `MESTORY_LLM_MODEL_VISION`(= gpt-5-mini) 반환
5. 두 경로 모두 ZDR·tools·json_object 옵션은 기존과 동일하게 붙는다.

**Edge Cases**

| # | 상황 | 처리 방식 |
|---|---|---|
| EC-01 | `MESTORY_LLM_MODEL_VISION` 미설정 | 이미지 유무와 무관하게 `MESTORY_LLM_MODEL` 사용 (= 현재 동작) |
| EC-02 | `MESTORY_LLM_MODEL_VISION`이 빈 문자열/공백 | 미설정과 동일 취급 (`.strip()` 후 판정) |
| EC-03 | `images=[]` (빈 리스트) | 이미지 없음으로 본다. `generate_report`의 기존 `has_images = bool(images)`를 그대로 쓴다 |
| EC-04 | vision 모델만 장애/404 | 기존 폴백 사다리가 그대로 동작한다. 모델을 바꿔 재시도하지 않는다(Out of Scope) |
| EC-05 | 로그·평가 기록의 모델명 | 실제로 라우팅된 모델을 기록한다. 안 고치면 "gpt-5-nano로 찍혔는데 실제로는 mini"가 된다 |

## How

**환경변수** (하나만 추가)

```
MESTORY_LLM_MODEL=openai/gpt-5-nano          # 기본·텍스트 경로 (기존 변수)
MESTORY_LLM_MODEL_VISION=openai/gpt-5-mini   # 신규. 없으면 위 값을 그대로 쓴다
```

**코드 변경 지점**

| 파일 | 변경 | 비고 |
|---|---|---|
| `backend/services/llm.py` | `resolve_model_name(has_images: bool) -> str` 신규 | `get_model_name()`은 **시그니처 그대로 유지** — 기존 테스트가 `lambda: "test-model"`로 monkeypatch 중이라 인자를 추가하면 깨진다 |
| `backend/services/llm.py` | `_build_llm(model: str \| None = None)` | 인자 없으면 기존대로 `get_model_name()` |
| `backend/services/llm.py` | `llm = _build_llm(resolve_model_name(has_images))` | `has_images`는 이미 함수 안에 있다 |
| `backend/main.py` | 완료 로그의 `get_model_name()` → 실제 라우팅된 모델 | **홍민하 님 파일 — 이 Spec으로 합의를 구한다.** import 1줄 + 호출 1줄 |
| `scripts/score_multimodal.py` | run 기록에 텍스트/이미지 모델을 각각 남긴다 | 라우팅 후에는 본 측정과 대조군의 모델이 달라져 단일 `model` 칸으로는 기록이 틀려진다 |

**제약**

- gpt-5-nano는 `scripts/check_zdr.py`로 검증 완료: ZDR+tools 200(Azure), 실사용 조건에서
  도구호출 O, `finish=tool_calls`, json_schema·json_object 4종 모두 통과.
- 후보 선정은 OpenRouter API에서 직접 읽은 단가·`supported_parameters`로 했다.
  446개 → tools+저가 109개 → batch/latest 제외 84개 → ZDR 실요청 200 61개 →
  `response_format`+`tool_choice` 56개 → 최종 1개.
- `google/gemini-2.5-flash-lite`는 **탈락**: 실사용 조건에서 도구를 호출하지 않고
  바로 답했고(`finish=stop`), `json_object`+`tools` 조합에서 빈 응답이 왔다.
- **비용 근거 수집**: `check_zdr.py` 출력은 쓸 수 없다. `prompt_tokens`를 찍지 않고,
  probe 요청의 입력 크기가 실제 요청(`SKILL.md` 전체가 프롬프트에 들어감)과 다르다.
  실제 `generate_report` 호출의 `usage`(Langfuse 트레이스)를 근거로 쓴다.
- 입력·출력 단가가 정확히 1/5이지만 **요청당 비용이 정확히 1/5이 되지는 않는다.**
  추론 토큰 수가 모델마다 달라 출력 토큰 수가 달라진다. 그래서 실측이 필요하다.

## AC (Given-When-Then)

**AC-01 · 환경변수가 없으면 회귀가 없다**
- GIVEN: `MESTORY_LLM_MODEL=openai/gpt-5-mini`, `MESTORY_LLM_MODEL_VISION` 미설정
- WHEN: `resolve_model_name(True)`와 `resolve_model_name(False)`를 부른다
- THEN: 둘 다 `"openai/gpt-5-mini"`를 반환한다

**AC-02 · 이미지 유무로 모델이 갈린다**
- GIVEN: `MESTORY_LLM_MODEL=openai/gpt-5-nano`, `MESTORY_LLM_MODEL_VISION=openai/gpt-5-mini`
- WHEN: `resolve_model_name(False)` / `resolve_model_name(True)`를 부른다
- THEN: 각각 `"openai/gpt-5-nano"` / `"openai/gpt-5-mini"`를 반환한다

**AC-03 · 빈 값은 미설정과 같다**
- GIVEN: `MESTORY_LLM_MODEL_VISION="  "` (공백만)
- WHEN: `resolve_model_name(True)`를 부른다
- THEN: `MESTORY_LLM_MODEL` 값을 반환한다 (AC-01과 동일 동작)

**AC-04 · 라우팅된 모델이 실제 LLM에 전달된다**
- GIVEN: `MESTORY_LLM_MODEL_VISION`이 설정된 상태
- WHEN: `_build_llm(resolve_model_name(True))`를 부른다
- THEN: 반환된 `ChatOpenAI`의 `model_name`이 vision 모델명과 일치한다

**AC-05 · 라우팅이 품질과 지연을 망가뜨리지 않는다**
- GIVEN: 라우팅이 켜진 상태
- WHEN: `scripts/score_multimodal.py --tag routed --retries 0` 을 **대조군까지 켜고**
  (`--no-image-control` 없이) 돌린다
- THEN: ① 이미지 경로의 `contract` 축이 기존 gpt-5-mini 범위(0.975~1.000) 아래로
  떨어지지 않는다. ② 이미지 없음 대조군의 최악1건 지연이 `GATE_TEXT_SEC` 이내다.
  하나라도 못 지키면 라우팅을 켜지 않고 그 사실을 `evals/EVAL_REPORT.md`에 적는다.

> ⚠️ 처음에 이 AC를 "대조군의 `contract` 축"으로 썼으나 **측정이 불가능했다.**
> `score_multimodal.py`의 대조군은 `visual_extraction`과 지연만 기록하고 `contract`는
> 재지 않는다. 그래서 텍스트 경로의 스키마 준수는 직접 못 재고, **재시도 횟수**
> (Langfuse 트레이스 수 ÷ 케이스 수)로 간접 확인한다.

**AC-06 · 비용 비교표가 실측으로 나온다**
- GIVEN: 라우팅 전후 각각의 측정 기록
- WHEN: Langfuse 트레이스에서 세션별 `total_cost` 합을 케이스 수로 나눈다
- THEN: `evals/EVAL_REPORT.md`에 "라우팅 전(전부 gpt-5-mini) vs 라우팅 후" 비교표가
  남는다. 측정 회차·케이스 수·재시도 배수를 함께 적는다.

> ⚠️ **트레이스 평균이 아니라 요청당으로 나눠야 한다.** 재시도가 있으면 트레이스 수가
> 케이스 수보다 많아져, 트레이스 평균을 쓰면 비용을 과소평가한다(실제로 2.5배 차이가 났다).
> 공시 단가를 곱하는 방식도 쓰지 않는다 — 프롬프트 캐싱 때문에 실제 과금과 맞지 않는다.
