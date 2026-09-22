"""두 평가 회차 비교 — scripts/eval_compare.py

Langfuse·LLM 없이 돈다. 가짜 회차 결과 파일을 임시 폴더에 써서 읽고, 비교 결과를 확인한다.
텍스트 회차 파일 모양은 run_langfuse_eval.py가 쓰는 evals/runs/langfuse_<회차>.json,
멀티모달은 score_multimodal.py가 쓰는 evals/runs/<회차>.json과 같다.
"""

import json

import pytest

from scripts.eval_compare import (
    MM_AXES, TEXT_AXES, check_same_dataset, compare_runs, format_axes, format_items, mm_items, text_items,
)

# 이 파일의 시험은 CSV/DB 데이터가 없어도 돌아간다 (conftest.py의 no_data 표시).
pytestmark = pytest.mark.no_data


def write_run(tmp_path, name, run):
    """가짜 회차 결과를 파일로 쓰고 다시 읽는다 — 실제 스크립트처럼 파일을 거친다."""
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(run, ensure_ascii=False), encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8"))


def text_row(case_id, status="ok", **scores):
    """텍스트 회차의 문항 한 줄. comments는 축마다 '<축> 이유'로 채운다."""
    return {"item_id": f"lf-{case_id}", "case_id": case_id, "status": status,
            "scores": scores, "comments": {axis: f"{axis} 이유 {case_id}" for axis in scores}}


def text_run(rows, fingerprint="aaaa1111"):
    return {"tag": "x", "text_dataset_fingerprint": fingerprint, "text": {"items": rows}}


def test_텍스트_회귀와_개선을_문항별로_찾고_이유를_붙인다(tmp_path):
    # 1번: judge_match 1 → 0 (회귀), 2번: judge_honesty 0 → 1 (개선), 3번: 그대로
    before = write_run(tmp_path, "before", text_run([
        text_row(1, contract=1.0, judge_match=1.0, judge_honesty=1.0, id_grounding=1.0),
        text_row(2, contract=1.0, judge_match=1.0, judge_honesty=0.0, id_grounding=1.0),
        text_row(3, contract=1.0, judge_match=0.5, judge_honesty=1.0, id_grounding=1.0),
    ]))
    after = write_run(tmp_path, "after", text_run([
        text_row(1, contract=1.0, judge_match=0.0, judge_honesty=1.0, id_grounding=1.0),
        text_row(2, contract=1.0, judge_match=1.0, judge_honesty=1.0, id_grounding=1.0),
        text_row(3, contract=1.0, judge_match=0.5, judge_honesty=1.0, id_grounding=1.0),
    ]))
    result = compare_runs(text_items(before), text_items(after), TEXT_AXES)

    # 회귀 1건: 1번 judge_match 1.0 → 0.0, 이유는 '이후' 회차의 그 축 판정 이유
    assert result["regressed"] == [("1", "judge_match", 1.0, 0.0, ["judge_match 이유 1"])]
    assert result["improved"] == [("2", "judge_honesty", 0.0, 1.0)]
    assert result["common"] == 3

    # 축별 평균 (손 계산)
    #   judge_match   : 이전 (1 + 1 + 0.5) / 3 = 0.8333…, 이후 (0 + 1 + 0.5) / 3 = 0.5
    #   judge_honesty : 이전 (1 + 0 + 1) / 3 = 0.6667…,  이후 (1 + 1 + 1) / 3 = 1.0
    before_mean, after_mean = result["axes"]["judge_match"]
    assert before_mean == pytest.approx(2.5 / 3) and after_mean == pytest.approx(0.5)
    assert result["axes"]["judge_honesty"] == (pytest.approx(2 / 3), pytest.approx(1.0))


def test_출력에_평균만이_아니라_회귀_문항_목록이_있다(tmp_path):
    # 평균이 같아도(0.5 → 0.5) 1번은 떨어지고 2번은 올랐다 — 목록이 없으면 이걸 못 본다
    before = write_run(tmp_path, "b", text_run([text_row(1, judge_match=1.0), text_row(2, judge_match=0.0)]))
    after = write_run(tmp_path, "a", text_run([text_row(1, judge_match=0.0), text_row(2, judge_match=1.0)]))
    result = compare_runs(text_items(before), text_items(after), ["judge_match"])
    text = "\n".join(format_axes(result, "b", "a") + format_items(result))

    assert "+0.000" in text                       # 평균은 그대로
    assert "회귀한 문항 1건" in text
    assert "❌ 1 judge_match 1.00 → 0.00" in text
    assert "└ judge_match 이유 1" in text
    assert "✅ 2 judge_match 0.00 → 1.00" in text


def test_인프라_오류로_못_잰_문항은_회귀로_세지_않는다(tmp_path):
    # 2번이 이후 회차에서 infra_error → contract 1 → 0이지만 모델 탓이 아니다
    before = write_run(tmp_path, "b", text_run([text_row(1, contract=1.0), text_row(2, contract=1.0)]))
    after = write_run(tmp_path, "a", text_run([text_row(1, contract=1.0), text_row(2, status="infra_error", contract=0.0)]))
    result = compare_runs(text_items(before), text_items(after), TEXT_AXES)

    assert result["regressed"] == []
    assert result["unmeasured"] == ["2"]
    assert result["common"] == 1
    assert any("측정 못 함(인프라 오류) 1건: 2" in line for line in format_items(result))


def test_옛_회차는_case_id가_없어_item_id로_짝을_맞춘다(tmp_path):
    # 2026-09-22 전 회차에는 case_id가 없다 → Langfuse 항목 id가 키가 된다
    old_row = {"item_id": "uuid-abc", "status": "ok", "scores": {"judge_match": 1.0}, "comments": {}}
    run = write_run(tmp_path, "old", {"text": {"items": [old_row]}})
    assert list(text_items(run)) == ["uuid-abc"]


def test_한쪽_회차에만_있는_축은_비교하지_않고_대시로_적는다(tmp_path):
    # 첫 회차(langfuse_baseline)에는 id_grounding 축이 없었다
    before = write_run(tmp_path, "b", text_run([text_row(1, judge_match=1.0)]))
    after = write_run(tmp_path, "a", text_run([text_row(1, judge_match=1.0, id_grounding=0.0)]))
    result = compare_runs(text_items(before), text_items(after), TEXT_AXES)

    assert result["regressed"] == []              # id_grounding 0.0이지만 비교 대상이 아니다
    assert result["axes"]["id_grounding"] == (None, 0.0)
    assert any("id_grounding" in line and "—" in line for line in format_axes(result, "b", "a"))


def test_공통_문항이_없으면_다른_평가셋이라고_알린다(tmp_path):
    # 옛 Dataset(UUID 키)과 새 Dataset(case_id 키)을 비교하는 경우
    before = write_run(tmp_path, "b", {"text": {"items": [
        {"item_id": "uuid-1", "status": "ok", "scores": {"judge_match": 1.0}, "comments": {}}]}})
    after = write_run(tmp_path, "a", text_run([text_row(1, judge_match=1.0)]))
    result = compare_runs(text_items(before), text_items(after), TEXT_AXES)

    assert result["common"] == 0
    assert result["only_before"] == ["uuid-1"] and result["only_after"] == ["1"]
    assert any("함께 잰 문항이 없습니다" in line for line in format_items(result))


@pytest.mark.parametrize("fp_before, fp_after, ok, has_message", [
    ("aaaa1111", "aaaa1111", True, False),        # 같은 평가셋 → 그냥 비교
    ("aaaa1111", "bbbb2222", False, True),        # 평가셋이 바뀜 → 비교하지 않는다
    (None, "aaaa1111", True, True),               # 옛 회차(지문 없음) → 경고하고 비교
])
def test_평가셋_지문으로_같은_평가셋인지_가른다(fp_before, fp_after, ok, has_message):
    same, message = check_same_dataset({"text_dataset_fingerprint": fp_before},
                                       {"text_dataset_fingerprint": fp_after})
    assert same is ok
    assert (message is not None) is has_message


def test_멀티모달_회차도_같은_로직으로_비교한다(tmp_path):
    # MM-01: contract 1.0 → 0.8 (회귀, 실패 이유 목록 전체를 붙인다), MM-02는 이후 회차에만 있음
    before = write_run(tmp_path, "b", {"cases": [
        {"id": "MM-01", "axes": {"visual_extraction": 1.0, "contract": 1.0}, "failed": []}]})
    after = write_run(tmp_path, "a", {"cases": [
        {"id": "MM-01", "axes": {"visual_extraction": 1.0, "contract": 0.8}, "failed": ["이유 가", "이유 나"]},
        {"id": "MM-02", "axes": {"visual_extraction": 1.0, "contract": 1.0}, "failed": []}]})
    result = compare_runs(mm_items(before), mm_items(after), MM_AXES)

    assert result["regressed"] == [("MM-01", "contract", 1.0, 0.8, ["이유 가", "이유 나"])]
    assert result["only_after"] == ["MM-02"]
    # 평균 (손 계산): contract 이전 1.0, 이후 (0.8 + 1.0) / 2 = 0.9
    assert result["axes"]["contract"] == (pytest.approx(1.0), pytest.approx(0.9))
