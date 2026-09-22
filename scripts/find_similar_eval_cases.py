"""평가셋(evals/dataset.jsonl) 품질 점검 — 오프라인 도구. 서비스 실행 경로와 무관하다.

하는 일 두 가지
  ① 겹치는 케이스 찾기: 질문 문장이 서로 너무 비슷한 두 건을 찾아 사람이 보게 한다.
     (LLM 프롬프트에 아무것도 넣지 않는다 — RAG가 아니다. 외부 임베딩 API도 안 쓴다.
     표준 라이브러리 difflib의 문자열 유사도만 쓴다 — 30건짜리 오프라인 점검에
     API 키·비용·네트워크를 끌어올 필요가 없다.)
  ② 빠진 유형 찾기: 에러코드 사전(docs/error_code_dict.csv)에 있는 코드인데 평가셋
     어느 질문에도 등장하지 않는 코드를 알려준다.

⚠️ 여기서 "비슷하다"고 나온 건 전부 사람이 읽고 판단할 것. 자동으로 지우지 않는다.
   backend/services/llm.py의 _dedupe_causes()에서 실측한 것처럼, 문자열 유사도는
   "온도"와 "진동"처럼 핵심 단어 하나만 달라도 꽤 비슷하다고 나올 수 있다.
   진짜 겹치는 케이스인지, 의도적으로 비슷하게 만든 경계 케이스인지는 이 스크립트가
   판단하지 않는다 — 후보만 보여준다.

쓰는 법 (저장소 루트에서):
    python scripts/find_similar_eval_cases.py
    python scripts/find_similar_eval_cases.py --threshold 0.5   # 후보를 더 넓게
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from itertools import combinations
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

DATASET = REPO_ROOT / "evals" / "dataset.jsonl"
DEFAULT_THRESHOLD = 0.75  # 사람이 훑어볼 후보를 보여주는 용도라, 런타임 중복 제거(0.97)보다 낮게 잡는다.
# 0.6까지 내리면 "이 설비의 정지 원인과..." 같은 공통 문구 때문에 후보가 너무 많아진다
# (실측: 30건에서 0.6 기준 20쌍, 0.75 기준 8쌍). --threshold로 필요할 때 낮출 수 있다.

_CODE_RE = re.compile(r"(?<![A-Za-z0-9-])[A-Z]{1,3}-\d{3}(?!\d)")


def load_cases() -> list[dict]:
    if not DATASET.exists():
        raise SystemExit(f"{DATASET} 없음")
    return [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def find_similar_pairs(cases: list[dict], threshold: float) -> list[tuple[dict, dict, float]]:
    pairs = []
    for a, b in combinations(cases, 2):
        ratio = difflib.SequenceMatcher(None, normalized(a["input"]), normalized(b["input"])).ratio()
        if ratio >= threshold:
            pairs.append((a, b, ratio))
    return sorted(pairs, key=lambda p: p[2], reverse=True)


def find_missing_codes(cases: list[dict]) -> list[str]:
    """에러코드 사전에는 있는데 평가셋 질문 어디에도 안 나오는 코드."""
    from mcp_server.tools.data_loader import load_error_codes

    known = sorted(str(c).strip() for c in load_error_codes()["error_code"].dropna().unique())
    mentioned = set()
    for case in cases:
        mentioned |= set(_CODE_RE.findall(case["input"]))
    return [c for c in known if c not in mentioned]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD, help=f"유사도 기준 (기본 {DEFAULT_THRESHOLD})")
    args = ap.parse_args()

    cases = load_cases()
    print(f"평가셋 {len(cases)}건 로드 ({DATASET.relative_to(REPO_ROOT)})\n")

    print(f"① 겹치는 케이스 후보 (유사도 ≥ {args.threshold}) — 사람이 확인할 것")
    pairs = find_similar_pairs(cases, args.threshold)
    if not pairs:
        print("  없음")
    for a, b, ratio in pairs:
        print(f"  {ratio:.2f}  #{a['id']}({a['note']}) ↔ #{b['id']}({b['note']})")
        print(f"        #{a['id']}: {a['input'][:80]}")
        print(f"        #{b['id']}: {b['input'][:80]}")

    print("\n② 에러코드 사전에는 있지만 평가셋에 한 번도 안 나온 코드")
    try:
        missing = find_missing_codes(cases)
    except Exception as exc:  # 데이터 소스가 없는 환경 등
        print(f"  건너뜀 — {type(exc).__name__}: {exc}")
        return
    if not missing:
        print("  없음 (사전의 모든 코드가 평가셋에 최소 한 번은 나온다)")
    else:
        print(f"  {len(missing)}개: {', '.join(missing)}")


if __name__ == "__main__":
    main()
