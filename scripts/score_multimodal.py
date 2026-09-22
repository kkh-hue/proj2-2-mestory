"""멀티모달 평가셋을 돌려 축별 점수를 내고, 회차끼리 비교한다.

필수 조건 4가 요구하는 것
  ① 측정 축을 2개 이상으로 나눈다 (종합 점수 하나로 뭉개면 무엇이 무너졌는지 안 보인다)
  ② **두 번 이상 재서** 어느 문항이 회귀했는지 숫자로 보인다
  이 스크립트가 둘 다 한다. --tag 로 회차를 남기고 --compare 로 비교한다.

측정 축 2개 (둘 다 규칙 기반 — judge 모델을 쓰지 않는다)
  visual_extraction : 이미지에서 읽어야 할 값을 담았는가 /
                      **가려서 안 보이는 값을 지어내지 않았는가**
  contract          : 스키마를 지켰는가 · used_image가 정확한가 ·
                      판정 불가 규칙을 지켰는가 · 사용자 입력을 덮어쓰지 않았는가

왜 judge를 안 쓰나
  이미지에서 읽은 값은 정답이 명확하다(labels.json). 이런 건 규칙으로 재는 게
  정확하고 싸고 재현된다. judge는 정답이 서술형인 텍스트 케이스에 쓰는 게 맞다.
  가이드도 "정확 일치·스키마 통과·규칙 기반·LLM-as-judge 모두 가능"이라고 했다.

실행 (proj2-2 폴더에서, venv 켠 상태)
    python scripts/score_multimodal.py --tag before
    ...무언가 하나만 바꾼 뒤...
    python scripts/score_multimodal.py --tag after
    python scripts/score_multimodal.py --compare before after

    --no-image-control 을 주면 '이미지 없이' 대조군을 건너뛴다(비용 절반)

비용 안내
  케이스 10건 × (이미지 있음 + 없음) = 호출 20번 ≈ $0.05.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import re
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
load_dotenv(REPO_ROOT / ".env")

IMAGES = REPO_ROOT / "evals" / "images"
DATASET = REPO_ROOT / "evals" / "dataset_multimodal.jsonl"
RUNS = REPO_ROOT / "evals" / "runs"        # 회차 결과 저장 위치

from backend.services.llm import (  # noqa: E402
    AnalysisInfrastructureError,
    generate_report,
    last_agent_steps,
    last_infra_error,
    resolve_model_name,
)
from mcp_server.tools.data_loader import load_error_codes          # noqa: E402
from scripts.latency_stats import p95                               # noqa: E402

# "E-102" 같은 에러코드 모양. 사전에 없는 것이 나오면 지어낸 것으로 본다.
#
# ⚠️ \b(단어 경계)를 쓰면 안 된다. Python 정규식에서 한글도 '단어 문자'라,
#    "X-777로 보임"처럼 한글이 바로 붙으면 7과 로 사이가 경계가 아니게 되어
#    매치가 통째로 실패한다. 한국어 응답에서는 거의 항상 이렇게 붙으므로
#    "지어낸 코드"를 영영 못 잡는다 (실제로 이 스크립트를 만들며 겪었다).
#    → 앞뒤를 ASCII 영숫자로만 막는다.
#
# ⚠️ 설비ID(EQ-020)·로그ID(LOG-011583)도 같은 모양이라 그대로 두면
#    "지어낸 코드"로 잘못 잡힌다(거짓 양성). 앞머리로 걸러낸다.
CODE_PATTERN = re.compile(r"(?<![A-Za-z0-9-])(?!EQ-|LOG-)[A-Z]{1,3}-\d{3}(?!\d)")


def known_codes() -> set[str]:
    """사전에 실제로 있는 코드 목록. '지어낸 코드' 판정의 기준이 된다."""
    return {str(r["error_code"]).strip() for _, r in load_error_codes().iterrows()}


def data_url(name: str) -> str:
    path = IMAGES / name
    if not path.exists():
        raise SystemExit(f"{path} 없음 → 먼저 `python scripts/make_hmi_images.py`")
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def load_cases() -> list[dict]:
    if not DATASET.exists():
        raise SystemExit(f"{DATASET} 없음 → 먼저 `python scripts/make_multimodal_evalset.py`")
    return [json.loads(l) for l in DATASET.read_text(encoding="utf-8").splitlines() if l.strip()]


# ─────────────────────────────────────────────
# 채점 — 축마다 여러 검사를 하고 '통과한 검사 / 전체 검사'로 점수를 낸다.
# 검사마다 왜 실패했는지 문장을 남긴다. 숫자만 남으면 나중에 원인을 못 찾는다.
# ─────────────────────────────────────────────
def score_case(case: dict, report, codes: set[str]) -> dict:
    ch = case["checks"]
    visual = " | ".join(report.visual_findings or [])
    cause_codes = [c.error_code for c in report.causes]
    severities = [c.severity for c in report.causes]

    v_checks: list[tuple[bool, str]] = []
    c_checks: list[tuple[bool, str]] = []

    # ── 축 1 · visual_extraction ──
    for token in ch.get("visual_must_include") or []:
        v_checks.append((token in visual, f"'{token}'를 읽어야 함"))

    for token in ch.get("visual_must_not_include") or []:
        # 가려진 값을 말하면 = 이미지에서 읽었다고 주장 = 지어냄
        v_checks.append((token not in visual, f"가려진 '{token}'를 말하면 안 됨"))

    if ch.get("visual_no_invented_code"):
        found = {m for m in CODE_PATTERN.findall(visual)}
        invented = sorted(found - codes)
        v_checks.append((not invented, f"사전에 없는 코드를 지어내면 안 됨 (발견: {invented or '없음'})"))

    if ch.get("visual_no_code_at_all"):
        # 화면에 에러코드가 아예 없는 경우(빈 코드 칸 · 무관한 이미지).
        # 이때는 '사전에 있는 코드'를 말해도 지어낸 것이다 —
        # 사전에 없는 코드만 잡는 위 검사로는 못 걸러진다.
        found = sorted(set(CODE_PATTERN.findall(visual)))
        v_checks.append((not found, f"화면에 코드가 없는데 코드를 말하면 안 됨 (발견: {found or '없음'})"))

    wrong = ch.get("visual_no_wrong_pairing")
    if wrong:
        bad = wrong["error_code_must_not_be"]
        # 라인ID가 '에러코드'라는 말과 붙어 나오면 짝을 잘못 맞춘 것
        mispaired = bool(re.search(rf"(에러\s*코드|error\s*code)[^|]*{re.escape(bad)}", visual, re.I))
        v_checks.append((not mispaired, f"'{bad}'를 에러코드로 읽으면 안 됨"))

    # ── 축 2 · contract ──
    c_checks.append((report.used_image is ch["used_image"],
                     f"used_image가 {ch['used_image']}여야 함 (실제 {report.used_image})"))

    want_id = ch.get("equipment_id_equals")
    if want_id:
        c_checks.append((report.equipment_id == want_id,
                         f"equipment_id가 사용자 입력 '{want_id}'여야 함 (실제 '{report.equipment_id}')"))

    sev = ch.get("severity_must_include")
    if sev:
        c_checks.append((sev in severities, f"severity에 '{sev}'가 있어야 함 (실제 {severities})"))

    for token in ch.get("cause_codes_must_not_include") or []:
        c_checks.append((token not in cause_codes,
                         f"'{token}'는 원인 목록에 없어야 함 (계획 정지)"))

    if ch.get("undeterminable_must_be_unconfirmed"):
        # 2026-09-22 rubric 결정: '판정 불가'는 is_confirmed=false까지 맞아야 정답 (SKILL.md 25줄).
        # '판정할 수 없다'면서 '확정'이라고 하면 현장에서 확정 판단으로 오해된다.
        bad = [c.error_code or "(빈 코드)" for c in report.causes if c.severity == "판정 불가" and c.is_confirmed]
        c_checks.append((not bad, f"'판정 불가' 원인은 is_confirmed=false여야 함 (위반: {bad or '없음'})"))

    mentions = ch.get("note_must_mention_any")
    if mentions:
        blob = (report.confidence_note or "") + " " + visual
        c_checks.append((any(m in blob for m in mentions),
                         f"{mentions} 중 하나를 언급해야 함"))

    # 스키마는 Pydantic이 이미 검증했다. 안전 응답으로 떨어졌는지만 본다.
    fell_back = "자동 분석 실패" in (report.confidence_note or "")
    c_checks.append((not fell_back, "안전 응답(폴백)으로 떨어지지 않아야 함"))

    def rate(checks):
        return 1.0 if not checks else sum(1 for ok, _ in checks if ok) / len(checks)

    return {
        "id": case["id"],
        "image": case["image"],
        "note": case["note"],
        "axes": {"visual_extraction": rate(v_checks), "contract": rate(c_checks)},
        "failed": [msg for ok, msg in v_checks + c_checks if not ok],
        "visual_findings": report.visual_findings,
        "used_image": report.used_image,
        "cause_codes": cause_codes,
        "severities": severities,
    }


RETRIES = 2        # --retries 로 덮어쓴다
RETRY_WAIT = 130   # --retry-wait 로 덮어쓴다 (402의 Retry-After가 120초였다)

# 지연 게이트. 옛 목표는 텍스트 10초 / 이미지 20초였는데, 그건 gpt-4o-mini 시절 숫자다.
# 보안 정책(ZDR) 때문에 tool calling과 ZDR을 동시에 만족하는 추론 모델로 갈아타면서
# 지연이 늘었고, 두 줄 다 지킬 수 없게 됐다. 그래서 실측 범위에 여유를 더해 다시 잡았다.
# 근거와 회차별 수치는 evals/EVAL_REPORT.md 에 있다.
GATE_TEXT_SEC = 24     # 실측 20.3초(gpt-5-mini, 1회) + 여유. 측정 회차가 1회뿐이라 근거가 얇다.
GATE_IMAGE_SEC = 28    # 실측 23.4~25.8초(6회) + 여유.


def run_case(case: dict, with_image: bool, *, tag: str = "adhoc",
             retries: int = RETRIES, wait_sec: int = RETRY_WAIT):
    """한 케이스를 돌린다. 폴백이 나오면 기다렸다 다시 시도한다.

    wait_sec 기본값이 130초인 이유: OpenRouter가 402(in_flight_budget_exhausted)와
    함께 주는 Retry-After 헤더가 120초였다. 여유를 조금 더 뒀다.

    llm.py는 인프라 오류를 AnalysisInfrastructureError로 올려 준다(예전에는 폴백
    리포트를 돌려줬다). 예외로 받는 쪽이 정확하다 — 모델이 우연히 비슷한 문장을
    적어 보낸 '정상 응답'과 헷갈리지 않기 때문이다.
    """
    kwargs = dict(case["request"])
    kwargs["images"] = [data_url(case["image"])] if with_image else None
    # Langfuse에서 회차별로 묶어 보기 위한 값.
    # 안 붙이면 모든 회차의 트레이스가 한 무더기로 섞여 "어느 회차 것인지" 알 수 없다.
    # (실제로 179건이 그렇게 섞여 있었다)
    # ⚠️ session_id가 아니라 trace_session_id다.
    #    session_id를 주면 DB에서 대화 기록을 찾는데, Windows에서는
    #    psycopg(Selector 루프)와 MCP 서브프로세스(Proactor 루프)가 충돌한다.
    #    평가는 '트레이스를 회차별로 묶는 이름표'만 필요하다.
    kwargs["trace_session_id"] = f"eval-{tag}{'' if with_image else '-noimg'}"
    kwargs["user_id"] = "eval-runner"

    report, elapsed = None, 0.0
    for attempt in range(retries + 1):
        t0 = time.perf_counter()
        try:
            report = asyncio.run(generate_report(**kwargs))
        except AnalysisInfrastructureError:
            # ⚠️ 이걸 0점으로 세면 안 된다. 모델이 틀린 게 아니라 측정을 못 한 것이다.
            #    실제로 그렇게 재서 contract 0.700이라는 틀린 숫자가 나온 적이 있다.
            report = None
        elapsed = time.perf_counter() - t0
        if report is not None:
            return report, elapsed, False

        # 폴백이 났다. 재시도할 가치가 있는 오류인지 llm.py가 남긴 원인을 보고 판단한다.
        # 401(키 만료)·404(설정 문제) 같은 건 백 번 해도 같은 결과다 —
        # 예전엔 이런 것도 130초씩 기다렸고, 키가 만료된 날 그대로 시간을 버렸다.
        info = last_infra_error() or {}
        if info.get("permanent"):
            print(f"        ⛔ 재시도해도 풀리지 않는 오류다 — "
                  f"{info.get('type')} {info.get('status_code')}")
            print(f"           {info.get('message', '')[:120]}")
            return report, elapsed, True

        if attempt < retries:
            reason = f" ({info.get('type')} {info.get('status_code')})" if info.get("type") else ""
            print(f"        ⏳ 폴백{reason} — 기다리면 풀릴 수 있는 오류다. "
                  f"{wait_sec}초 후 재시도 ({attempt + 1}/{retries})")
            time.sleep(wait_sec)

    return None, elapsed, True  # 끝까지 실패 = 측정 불가 (report는 쓰지 않는다)


def do_run(tag: str, skip_control: bool) -> dict:
    cases = load_cases()
    codes = known_codes()
    # 라우팅이 켜져 있으면 본 측정(이미지 O)과 대조군(이미지 X)이 서로 다른 모델로 간다.
    # 같은 줄에 둘 다 찍어 둬야 나중에 결과를 볼 때 어느 모델 수치인지 헷갈리지 않는다.
    model_vision, model_text = resolve_model_name(True), resolve_model_name(False)
    routing = f"{model_vision} (이미지) / {model_text} (텍스트)" if model_vision != model_text else model_vision
    print(f"모델 {routing} · 케이스 {len(cases)}건 · 회차 '{tag}'\n")

    scored, latencies, control = [], [], []
    unmeasured = []          # 인프라 오류로 끝내 못 잰 케이스 — 점수에서 제외한다
    degraded = []            # 축소 스키마로 떨어진 케이스 — 점수는 세되 표시한다
    for case in cases:
        report, sec, failed_infra = run_case(case, with_image=True, tag=tag)

        if failed_infra:
            # ⚠️ 0점으로 세지 않는다. 모델이 틀린 게 아니라 측정을 못 한 것이다.
            unmeasured.append(case["id"])
            print(f"  ⚠️  {case['id']}  측정 불가 (인프라 오류로 폴백) — 점수에서 제외")

            # 첫 두 건이 연달아 실패하면 일시적 오류가 아니라 설정 문제다.
            # (겪은 예: API 키가 ZDR 걸린 계정 소속 → 몇 번을 재시도해도 404)
            # 그대로 두면 케이스마다 130초씩 기다리며 20분을 버린다. 즉시 멈춘다.
            if len(unmeasured) == 2 and not scored:
                print("\n  ⛔ 처음 두 건이 모두 실패했다. 일시적 오류가 아니라 설정 문제로 보인다.")
                print("     재시도를 멈춘다. 확인할 것:")
                print("       · .env의 OPENROUTER_API_KEY가 맞는 계정의 키인가")
                print("       · 그 계정의 크레딧 잔액 (402) / ZDR 설정 (404)")
                print("       · 자세한 원인은 위 로그의 'MCP 연결 또는 에이전트 실행 중 오류' 줄")
                raise SystemExit(1)
            continue

        latencies.append(sec)
        steps = last_agent_steps()
        result = score_case(case, report, codes)
        result["elapsed_sec"] = round(sec, 2)
        # 느린 케이스가 '모델이 느린 것'인지 '도구를 여러 번 왕복한 것'인지
        # 나중에 가려내려면 횟수가 함께 남아야 한다.
        result["tool_calls"] = steps
        scored.append(result)
        # 축소 스키마로 떨어졌으면 causes가 비어 있다 — 점수가 조용히 낮아진다.
        # 폴백(측정 불가)과 달리 '정상 응답'처럼 보이므로 따로 알린다.
        if "축소 스키마 응답" in (report.confidence_note or ""):
            degraded.append(case["id"])
            print(f"        ⚠️  축소 스키마로 응답함 — causes가 비어 점수가 낮게 나온다. "
                  f"출력이 잘렸는지(MAX_OUTPUT_TOKENS) 로그 확인")

        mark = "✅" if not result["failed"] else "❌"
        print(f"  {mark} {result['id']}  visual={result['axes']['visual_extraction']:.2f} "
              f"contract={result['axes']['contract']:.2f}  {sec:.1f}s  도구 {steps if steps is not None else '?'}회")
        for msg in result["failed"]:
            print(f"        └ {msg}")

        # 이미지 없이 같은 조건 — '이미지가 실제로 기여했다'는 증거 (S-2)
        if not skip_control and case["checks"]["used_image"]:
            ctrl, csec, ctrl_infra = run_case(case, with_image=False, tag=tag)
            if ctrl_infra:
                # 대조군이 폴백이면 그 차이가 이미지 덕분인지 오류 탓인지 알 수 없다.
                print(f"        ⚠️  {case['id']} 대조군 측정 불가 — 기여도 계산에서 제외")
            else:
                ctrl_res = score_case(case, ctrl, codes)
                control.append({"id": case["id"],
                                "visual_extraction": ctrl_res["axes"]["visual_extraction"],
                                "elapsed_sec": round(csec, 2)})

    def mean(xs):
        return round(statistics.mean(xs), 4) if xs else 0.0

    # p95는 scripts/latency_stats.py의 선형보간 p95를 쓴다.
    # 옛 계산은 10건이면 최댓값을 돌려줘서 출력에서 '최악1건'이라고 불렀다 — 이제는 이름 그대로 p95다.
    summary = {
        "tag": tag,
        "when": datetime.now().isoformat(timespec="seconds"),
        # "model"은 기존 회차 파일과 키를 맞추려고 그대로 둔다(본 측정 = 이미지 있음).
        # 라우팅이 켜지면 대조군은 다른 모델이므로 model_no_image를 따로 남긴다.
        "model": model_vision,
        "model_no_image": model_text,
        "n": len(scored),
        "unmeasured": unmeasured,   # 인프라 오류로 못 잰 케이스 — 보고서에 반드시 밝힌다
        "degraded": degraded,       # 축소 스키마로 떨어진 케이스
        "axes": {
            "visual_extraction": mean([r["axes"]["visual_extraction"] for r in scored]),
            "contract": mean([r["axes"]["contract"] for r in scored]),
        },
        "latency": {"mean": mean(latencies), "p95": p95(latencies)},
        "control_no_image": {
            "visual_extraction": mean([c["visual_extraction"] for c in control]),
            "p95": p95([c["elapsed_sec"] for c in control]),
        } if control else None,
        "cases": scored,
    }

    RUNS.mkdir(parents=True, exist_ok=True)
    path = RUNS / f"{tag}.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 70)
    n_ok, n_all = summary["n"], summary["n"] + len(summary["unmeasured"])
    print(f"  visual_extraction : {summary['axes']['visual_extraction']:.3f}  ({n_ok}/{n_all}건 기준)")
    print(f"  contract          : {summary['axes']['contract']:.3f}  ({n_ok}/{n_all}건 기준)")
    if summary.get("degraded"):
        print(f"\n  ⚠️  축소 스키마 {len(summary['degraded'])}건: {', '.join(summary['degraded'])}")
        print("      causes가 비어 점수가 실제보다 낮다. 출력 잘림 여부를 확인하라.")
    if summary["unmeasured"]:
        print(f"\n  ⚠️  측정 불가 {len(summary['unmeasured'])}건: {', '.join(summary['unmeasured'])}")
        print("      인프라 오류(폴백)로 점수에서 제외했다. 모델 실패가 아니다.")
        print("      → 이 상태의 점수는 보고서에 쓰지 말고, 전건 측정 후 다시 재라.")
    print(f"  지연 평균/p95       : {summary['latency']['mean']:.1f}s / {summary['latency']['p95']:.1f}s")
    if control:
        c = summary["control_no_image"]
        gap = summary["axes"]["visual_extraction"] - c["visual_extraction"]
        print(f"\n  [이미지 기여] 이미지 있음 {summary['axes']['visual_extraction']:.3f} "
              f"vs 없음 {c['visual_extraction']:.3f}  → 차이 {gap:+.3f}")
        # 게이트는 EVAL_REPORT에 "최악 1건 ≤ 24s / 28s"로 정해져 있다 — p95가 아니라 최댓값으로 판정한다.
        # (옛 p95는 10건이면 최댓값이었으므로, 여기를 p95로 바꾸면 게이트가 말없이 느슨해진다)
        text_worst = max(x["elapsed_sec"] for x in control)
        image_worst = max(latencies, default=0.0)
        print(f"  [게이트] 텍스트 최악1건 {text_worst:.1f}s (목표 {GATE_TEXT_SEC}s) / "
              f"이미지 최악1건 {image_worst:.1f}s (목표 {GATE_IMAGE_SEC}s)")
    slow = sorted((r for r in summary["cases"]), key=lambda r: -r["elapsed_sec"])[:3]
    if slow:
        print("\n  [느린 케이스 3건]  지연 / 도구호출")
        for r in slow:
            print(f"    {r['id']}  {r['elapsed_sec']:5.1f}s  도구 {r.get('tool_calls', '?')}회")
        print("    → 도구 횟수가 같은데 느리면 모델 지연, 많으면 왕복 때문이다.")

    print(f"\n  저장: evals/runs/{tag}.json")
    return summary


def do_compare(before: str, after: str) -> None:
    """두 회차를 나란히 놓고 **어느 문항이 회귀했는지** 보여준다.
    필수 조건 4가 요구하는 건 평균이 올랐다는 말이 아니라 이 목록이다."""
    a = json.loads((RUNS / f"{before}.json").read_text(encoding="utf-8"))
    b = json.loads((RUNS / f"{after}.json").read_text(encoding="utf-8"))

    print(f"{'축':20s} {before:>10s} → {after:>10s}   변화")
    for axis in ("visual_extraction", "contract"):
        x, y = a["axes"][axis], b["axes"][axis]
        print(f"  {axis:18s} {x:10.3f} → {y:10.3f}   {y - x:+.3f}")
    # 저장된 latency.p95는 옛 회차면 옛 공식(10건이면 최댓값)으로 계산된 값이다.
    # 두 회차를 같은 공식으로 비교하려고 케이스별 원본 지연(elapsed_sec)에서 다시 계산한다.
    a_p95 = p95([c["elapsed_sec"] for c in a["cases"]])
    b_p95 = p95([c["elapsed_sec"] for c in b["cases"]])
    print(f"  {'p95(초)':18s} {a_p95:10.1f} → {b_p95:10.1f}   {b_p95 - a_p95:+.1f}")

    a_case = {c["id"]: c for c in a["cases"]}
    regressed, improved = [], []
    for c in b["cases"]:
        old = a_case.get(c["id"])
        if not old:
            continue
        for axis in ("visual_extraction", "contract"):
            d = c["axes"][axis] - old["axes"][axis]
            if d < 0:
                regressed.append((c["id"], axis, old["axes"][axis], c["axes"][axis], c["failed"]))
            elif d > 0:
                improved.append((c["id"], axis, old["axes"][axis], c["axes"][axis]))

    print(f"\n  회귀한 문항 {len(regressed)}건")
    for cid, axis, x, y, failed in regressed:
        print(f"    ❌ {cid} {axis} {x:.2f} → {y:.2f}")
        for m in failed:
            print(f"         └ {m}")
    print(f"\n  좋아진 문항 {len(improved)}건")
    for cid, axis, x, y in improved:
        print(f"    ✅ {cid} {axis} {x:.2f} → {y:.2f}")
    print("\n  이 표와 회귀 목록을 EVAL_REPORT.md 4장에 그대로 옮기면 된다.")


def main() -> None:
    global RETRIES, RETRY_WAIT   # --retries/--retry-wait 로 덮어쓴다
    ap = argparse.ArgumentParser(description="멀티모달 평가셋 채점")
    ap.add_argument("--tag", help="회차 이름 (예: before, after, gpt4o)")
    ap.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"))
    ap.add_argument("--no-image-control", action="store_true", help="이미지 없음 대조군 생략")
    ap.add_argument("--retries", type=int, default=RETRIES,
                    help=f"폴백 시 재시도 횟수 (기본 {RETRIES}, 0이면 재시도 안 함)")
    ap.add_argument("--retry-wait", type=int, default=RETRY_WAIT,
                    help=f"재시도 전 대기 초 (기본 {RETRY_WAIT})")
    args = ap.parse_args()
    RETRIES, RETRY_WAIT = args.retries, args.retry_wait

    if args.compare:
        do_compare(*args.compare)
        return
    if not args.tag:
        ap.error("--tag 또는 --compare 중 하나가 필요합니다")
    if not os.getenv("OPENROUTER_API_KEY"):
        raise SystemExit("OPENROUTER_API_KEY가 없습니다 (.env 확인)")
    do_run(args.tag, args.no_image_control)


if __name__ == "__main__":
    main()
