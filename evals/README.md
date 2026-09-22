# 평가셋

필수 조건 4 — **최소 30건**. 개선 전후를 같은 셋으로 비교합니다.

## 구성

| 종류 | 왜 필요한가 |
|---|---|
| 정상 케이스 | 기본 동작 확인 |
| 경계 케이스 | 애매한 입력에서 어떻게 되는지 |
| 실패 유도 | 유해·부적절 입력, 스키마를 깨는 입력 |

**잘 되는 것만 모으면 평가가 아니라 자랑입니다.** 실패 사례를 반드시 넣으세요.

## 만드는 시점

**프로젝트 초반(9/23까지)에 만듭니다.** 나중에 만들면 이미 튜닝된 결과에 맞춰집니다.
추석 연휴(9/24~27) 전에 문제 정의와 이 평가셋이 확정돼 있어야 연휴 동안 각자 진행할 수 있습니다.

## 판정 방식

정확 일치 · 스키마 통과 여부 · 규칙 기반 채점 · LLM-as-judge 모두 가능합니다.
다만 **어떤 방식이고 그 방식의 한계가 무엇인지** 리포트에 적어야 합니다.

> LLM-as-judge를 쓴다면 생성 모델과 판정 모델을 같은 것으로 두지 마세요. 후한 점수가 나옵니다.

## 현재 구성 (9/20 기준)

| 파일·폴더 | 내용 |
|---|---|
| `dataset.jsonl` | 텍스트 평가셋 **30건** — 각 행에 `input`(질문), `expected`(기대 답), `note`(케이스 종류), `why`(정답 근거) |
| `dataset_multimodal.jsonl` | 이미지 첨부 평가셋 **10건** (`MM-01`~) — `image`, `request`, `input`, `expected`, `note`, `why` |
| `images/` | 멀티모달 평가에 쓰는 HMI 알람 화면 이미지 (정상·경계·실패 유도) |
| `runs/` | 회차별 측정 기록(`before.json`, `after*.json`, `gpt5mini.json`, `noise*.json` 등) — 개선 전후·모델 교체·재측정 비교용 |

멀티모달 평가셋과 이미지는 손으로 만들지 않고 스크립트로 생성·채점합니다(정답이 이미지에 실제로 적힌 값과 어긋나지 않게).

```bash
python scripts/make_hmi_images.py         # 평가용 HMI 이미지 생성
python scripts/make_multimodal_evalset.py # dataset_multimodal.jsonl 생성
python scripts/score_multimodal.py --tag <회차명>          # 축별 점수 측정 (runs/에 기록)
python scripts/score_multimodal.py --compare <회차A> <회차B> # 회차 비교
```

Langfuse Dataset으로 텍스트 30건 + 멀티모달 10건을 한 번에 돌리고 회차별로 기록합니다(판정 모델은 생성 모델과 다른 회사 모델).

```bash
python scripts/run_langfuse_eval.py --tag <회차명>            # 텍스트 + 멀티모달
python scripts/run_langfuse_eval.py --tag <회차명> --only text --limit 3   # 시험 실행
python scripts/run_langfuse_eval.py --compare <회차A> <회차B>  # 텍스트 두 회차 비교 (Langfuse·LLM 호출 없음, 비용 없음)
```

예) 무언가를 바꾸기 전후로 텍스트 30건을 재고 비교한다:

```bash
python scripts/run_langfuse_eval.py --tag before --only text
# … SKILL.md·프롬프트 등 하나만 바꾼다 …
python scripts/run_langfuse_eval.py --tag after --only text
python scripts/run_langfuse_eval.py --compare before after
```

- `--compare`는 축별 평균의 변화와 **떨어진 문항 목록**(문항 번호·축·점수·판정 이유)을 보여 준다. 인프라 오류로 못 잰 문항은 회귀로 세지 않고 따로 적는다.
- 텍스트 Dataset은 `dataset.jsonl`에서 **자동으로 만든다**. 이름은 `mestory-text-30-<내용 지문 8자리>`라서, 평가셋이 바뀌면 새 Dataset이 생기고 옛 내용으로 도는 일이 없다.
- 회차 파일에 평가셋 지문이 남는다. `--compare`는 **지문이 다른 두 회차를 비교하지 않는다**(평가셋이 바뀌었으면 '회귀'가 모델 탓인지 문항 탓인지 가를 수 없다).
- 2026-09-21에 CSV로 올린 `30개 이상 데이터셋`으로 잰 옛 회차(`langfuse_baseline` 등)는 확정(9/22) 전 내용이고 문항 id도 달라, 새 회차와 문항별 비교가 되지 않는다. 옛 회차끼리는 비교된다.

평가셋 자체를 점검할 때는(겹치는 케이스, 사전에는 있지만 평가셋에 없는 에러코드) 아래 오프라인 도구를 씁니다. LLM 호출도, 비용도 없습니다(문자열 유사도만 씁니다).

```bash
python scripts/find_similar_eval_cases.py
```

- 결과는 Langfuse의 Datasets → Experiments와 `runs/langfuse_<회차명>.json`에 남습니다. 자세한 채점 축·한계는 루트 [EVAL_REPORT.md](../EVAL_REPORT.md) 3장.
- 리포트 저장은 건너뜁니다. OpenRouter 크레딧이 남은 키가 필요하고, DB 없이 돌리려면 `MESTORY_DATA_SOURCE=csv`, `MESTORY_DATA_DIR=<CSV 폴더>`를 줍니다.

- 측정은 **두 번 이상** 재서 회차 간 차이를 봅니다. 같은 조건에서도 점수가 달라질 수 있어(노이즈) 보고서에는 한 번의 값이 아니라 범위로 적습니다.
- 점수·개선 전후 해석은 루트의 [EVAL_REPORT.md](../EVAL_REPORT.md)에 정리합니다.
