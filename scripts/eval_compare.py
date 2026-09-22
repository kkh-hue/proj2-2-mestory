"""두 평가 회차를 문항별로 대조한다 — 멀티모달(score_multimodal.py)과 텍스트(run_langfuse_eval.py)가 같이 쓴다.

왜 따로 파일을 두나
  두 채점 스크립트는 import되는 순간 .env를 읽는다(run_langfuse_eval.py는 Langfuse 연결과
  save_report 바꿔치기까지 한다). 테스트가 그 파일을 불러오면 환경변수가 섞여 다른 테스트가 깨진다.
  이 파일은 표준 라이브러리만 써서 불러와도 부작용이 없다 (scripts/latency_stats.py와 같은 이유).

문항 한 건의 모양 — 각 스크립트는 자기 회차 파일을 이 모양으로 바꿔서 넘긴다 (mm_items / text_items)
  {"scores": {축: 점수}, "notes": [실패 이유, ...] 또는 {축: 이유}, "measured": True/False}
  measured=False = 인프라 오류로 못 잰 문항. 모델이 틀린 게 아니므로 회귀로 세지 않는다.

왜 평균만 보여주지 않나
  평균이 그대로여도 한 문항이 떨어지고 다른 문항이 올랐을 수 있다. 필수 조건 4가 요구하는 것은
  "어느 문항이 회귀했는가"이므로 문항별 목록이 이 모듈의 핵심이다.
"""

from __future__ import annotations

import statistics

MM_AXES = ["visual_extraction", "contract"]
TEXT_AXES = ["contract", "judge_match", "judge_honesty", "id_grounding"]


# ─────────────────────────────────────────────
# 1단계 · 회차 파일 → 문항 모양 (어댑터)
# ─────────────────────────────────────────────
def mm_items(run: dict) -> dict[str, dict]:
    """score_multimodal.py 회차 파일(evals/runs/<tag>.json) → 문항 모양.

    측정 불가 케이스는 애초에 cases에 들어가지 않으므로(unmeasured에 따로 적힌다) 전부 measured=True다.
    """
    return {
        c["id"]: {"scores": dict(c["axes"]), "notes": list(c.get("failed") or []), "measured": True}
        for c in run["cases"]
    }


def text_items(run: dict) -> dict[str, dict]:
    """run_langfuse_eval.py 회차 파일(evals/runs/langfuse_<tag>.json)의 text 부분 → 문항 모양.

    짝을 맞추는 키는 평가셋의 id(case_id)다. Langfuse 항목 id는 Dataset마다 달라서 키로 못 쓴다.
    2026-09-22 전 회차에는 case_id가 없어 Langfuse 항목 id로 대신한다(같은 Dataset끼리만 짝이 맞는다).
    """
    items = {}
    for row in run["text"]["items"]:
        key = row.get("case_id")
        key = str(key) if key is not None else str(row.get("item_id"))
        items[key] = {
            "scores": dict(row.get("scores") or {}),
            "notes": dict(row.get("comments") or {}),
            "measured": row.get("status") != "infra_error",
        }
    return items


def check_same_dataset(before_run: dict, after_run: dict) -> tuple[bool, str | None]:
    """두 텍스트 회차가 같은 평가셋에서 잰 것인지 본다. (비교해도 되는가, 알릴 말)

    평가셋이 바뀌었는데 비교하면 "회귀"가 모델이 나빠진 건지 문항이 바뀐 건지 가를 수 없다.
    """
    fb = before_run.get("text_dataset_fingerprint")
    fa = after_run.get("text_dataset_fingerprint")
    if fb and fa and fb != fa:
        return False, (f"두 회차의 평가셋 지문이 다릅니다 ({fb[:8]} ≠ {fa[:8]}). "
                       "평가셋 내용이 바뀌어 문항별 비교가 의미 없으므로 비교하지 않습니다.")
    if not fb or not fa:
        return True, ("평가셋 지문이 없는 회차가 있습니다(2026-09-22 전 회차 등). "
                      "같은 평가셋인지 확인할 수 없어 문항 ID로만 짝을 맞춥니다.")
    return True, None


# ─────────────────────────────────────────────
# 2단계 · 비교
# ─────────────────────────────────────────────
def _mean(items: dict[str, dict], axis: str) -> float | None:
    """그 축 점수가 있는 문항의 평균. 한 건도 없으면 None (옛 회차에 없던 축)."""
    values = [it["scores"][axis] for it in items.values() if axis in it["scores"]]
    return statistics.mean(values) if values else None


def compare_runs(before: dict[str, dict], after: dict[str, dict], axes: list[str]) -> dict:
    """두 회차를 문항별로 대조한다.

    돌려주는 것
      axes        : {축: (이전 평균, 이후 평균)}. 각 회차에서 그 축 점수가 있는 문항의 평균
      regressed   : [(문항ID, 축, 이전, 이후, 이유 목록)]. 점수가 떨어진 문항 — 이게 핵심이다
      improved    : [(문항ID, 축, 이전, 이후)]
      common      : 두 회차 모두에서 잰 문항 수
      unmeasured  : 한쪽이라도 못 잰 문항 ID (비교에서 뺐다)
      only_before / only_after : 한쪽 회차에만 있는 문항 ID
    """
    regressed, improved, unmeasured = [], [], []
    common = 0
    # 이후 회차의 순서대로 본다 — 사람이 읽을 때 평가셋 순서와 같게
    for item_id, new in after.items():
        old = before.get(item_id)
        if old is None:
            continue
        if not (old["measured"] and new["measured"]):
            unmeasured.append(item_id)
            continue
        common += 1
        for axis in axes:
            if axis not in old["scores"] or axis not in new["scores"]:
                continue        # 한쪽 회차에 없던 축은 비교하지 않는다
            x, y = old["scores"][axis], new["scores"][axis]
            if y < x:
                notes = new["notes"]
                reasons = list(notes) if isinstance(notes, list) else [notes[axis]] if notes.get(axis) else []
                regressed.append((item_id, axis, x, y, reasons))
            elif y > x:
                improved.append((item_id, axis, x, y))
    return {
        "axes": {axis: (_mean(before, axis), _mean(after, axis)) for axis in axes},
        "regressed": regressed,
        "improved": improved,
        "common": common,
        "unmeasured": unmeasured,
        "only_before": [k for k in before if k not in after],
        "only_after": [k for k in after if k not in before],
    }


# ─────────────────────────────────────────────
# 3단계 · 사람이 읽는 출력
# ─────────────────────────────────────────────
def format_axes(result: dict, before_tag: str, after_tag: str) -> list[str]:
    """축별 평균의 변화. 옛 회차에 없던 축은 '—'로 적는다."""
    lines = [f"{'축':20s} {before_tag:>10s} → {after_tag:>10s}   변화"]
    for axis, (x, y) in result["axes"].items():
        if x is None or y is None:
            left = f"{x:10.3f}" if x is not None else f"{'—':>10s}"
            right = f"{y:10.3f}" if y is not None else f"{'—':>10s}"
            lines.append(f"  {axis:18s} {left} → {right}   (점수가 없는 회차가 있어 비교하지 않음)")
        else:
            lines.append(f"  {axis:18s} {x:10.3f} → {y:10.3f}   {y - x:+.3f}")
    return lines


def format_items(result: dict) -> list[str]:
    """회귀한 문항 → 좋아진 문항 → 비교에서 뺀 문항 순서로 적는다."""
    lines = [f"\n  회귀한 문항 {len(result['regressed'])}건"]
    for item_id, axis, x, y, reasons in result["regressed"]:
        lines.append(f"    ❌ {item_id} {axis} {x:.2f} → {y:.2f}")
        lines.extend(f"         └ {m}" for m in reasons)
    lines.append(f"\n  좋아진 문항 {len(result['improved'])}건")
    for item_id, axis, x, y in result["improved"]:
        lines.append(f"    ✅ {item_id} {axis} {x:.2f} → {y:.2f}")

    # 아래는 해당할 때만 적는다 (멀티모달의 기존 출력은 여기까지와 한 글자도 같다)
    left_out = []
    if result["unmeasured"]:
        left_out.append(f"    측정 못 함(인프라 오류) {len(result['unmeasured'])}건: {', '.join(result['unmeasured'])}")
    if result["only_before"]:
        left_out.append(f"    이전 회차에만 있음 {len(result['only_before'])}건: {', '.join(result['only_before'])}")
    if result["only_after"]:
        left_out.append(f"    이후 회차에만 있음 {len(result['only_after'])}건: {', '.join(result['only_after'])}")
    if left_out:
        lines.append(f"\n  비교에서 뺀 문항 (두 회차 모두에서 잰 문항 {result['common']}건만 비교했다)")
        lines.extend(left_out)
    if result["common"] == 0:
        lines.append("\n  ⚠️ 두 회차에 함께 잰 문항이 없습니다 — 다른 평가셋(Dataset)에서 잰 회차로 보입니다.")
    return lines
