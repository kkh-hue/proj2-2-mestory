"""Langfuse Dataset으로 평가를 돌린다 — 텍스트 30건 + 멀티모달 10건.

하는 일
  ① 텍스트: evals/dataset.jsonl에서 Langfuse Dataset을 (없으면) 만들고, 항목을 분석기(generate_report)에
     넣어 결과를 **LLM 판정 + 규칙**으로 채점해 Langfuse에 기록한다.
     Dataset 이름에 평가셋 내용의 지문을 넣는다(mestory-text-30-<지문 8자리>) — jsonl이 바뀌면
     새 Dataset이 생겨, 옛 내용으로 도는 일이 없다. jsonl은 읽기만 한다(강경희 님 담당).
  ② 멀티모달: evals/dataset_multimodal.jsonl에서 Langfuse Dataset을 (없으면) 만들고,
     scripts/score_multimodal.py와 **같은 규칙 채점**(visual_extraction · contract)으로 돌린다.
     이미지는 base64로 Langfuse에 올리지 않는다(멀티모달 Spec AC-10). 파일명만 넣고
     실제 이미지는 이 스크립트가 로컬에서 읽어 붙인다.

측정 축 (텍스트)
  contract      : 인프라 오류·폴백 없이 처리됐는가 (규칙). 400·422로 거절한 것은 정상 처리다.
  judge_match   : 기대 답의 핵심 판정(원인·심각도·거절/판정 불가)과 일치하는가 (LLM 판정, 0 / 0.5 / 1)
  judge_honesty : 근거가 부족한 곳을 확정처럼 단정하지 않았는가 (LLM 판정, 0 / 1)
  id_grounding  : 출력이 인용한 정비(MT-)·정지(LOG-) 기록 ID가 실제 데이터에 있는가 (규칙, 0 / 1)
                  — 판정 모델은 DB를 못 봐서 '지어냈다'고 잘못 판정한다. 존재 여부는 규칙이 잰다.

판정 방식과 한계 (EVAL_REPORT.md 3-1)
  - 판정 모델은 생성 모델(openai/gpt-5-mini)과 **다른 회사 모델**을 쓴다(기본 anthropic/claude-haiku-4.5).
    같은 모델이 자기 답을 채점하면 후한 점수가 나온다.
  - 경계 케이스는 정해진 정답이 없다. 이런 항목은 '정답 일치'가 아니라
    '판단 근거를 제시하고 잠정·사람 확인을 밝혔는가'로 채점하도록 판정 프롬프트에 적었다.
  - 판정 모델도 틀린다. 채점 이유(comment)를 Langfuse에 남기니 사람이 훑어 볼 것.

실행 (저장소 루트, venv 켠 상태, OpenRouter 크레딧이 남은 키가 환경변수에 있어야 한다)
    python scripts/run_langfuse_eval.py --tag before
    python scripts/run_langfuse_eval.py --tag after --only text
    python scripts/run_langfuse_eval.py --tag smoke --limit 3

  MESTORY_DATA_SOURCE=csv, MESTORY_DATA_DIR=docs 로 돌리면 DB 없이 CSV로 조회한다.
  리포트 저장(save_report)은 하지 않는다 — 평가가 운영 DB에 리포트를 쌓으면 안 된다.

비용 (Langfuse에 쌓인 실측 기준): 텍스트 리포트 1건 평균 ≈ $0.0033.
  30건 + 멀티모달 10건 + 판정 = 한 회차에 대략 $0.2~0.4.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))
load_dotenv(REPO_ROOT / ".env")

from langfuse import Evaluation, get_client  # noqa: E402

import backend.services.llm as llm  # noqa: E402
from backend.services.llm import AnalysisInfrastructureError, generate_report  # noqa: E402

RUNS = REPO_ROOT / "evals" / "runs"
TEXT_DATASET_FILE = REPO_ROOT / "evals" / "dataset.jsonl"
MM_DATASET_FILE = REPO_ROOT / "evals" / "dataset_multimodal.jsonl"
# 2026-09-21에 CSV로 올린 Dataset. 강경희 님의 확정(2026-09-22, 7문항 변경) **전** 내용이다.
# 기본값으로 쓰지 않는다 — 옛 회차를 그대로 재현할 때만 --text-dataset으로 지정한다.
LEGACY_TEXT_DATASET = "30개 이상 데이터셋"
DEFAULT_MM_DATASET = "멀티모달 10건 평가셋"
DEFAULT_JUDGE = "anthropic/claude-haiku-4.5"


# 평가가 운영 DB에 리포트를 쌓으면 안 된다. 저장만 건너뛰고 나머지 경로는 그대로 탄다.
async def _no_save(*args, **kwargs):
    return None


llm.save_report = _no_save


# ─────────────────────────────────────────────
# 텍스트 케이스: 입력 문장 → 요청 조건
# ─────────────────────────────────────────────
_TAG_RE = re.compile(r"^\[(?P<tag>[^\]]*)\]\s*(?P<question>.*)$", re.DOTALL)
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def parse_text_input(text: str) -> dict:
    """'[LINE-A / EQ-004 / M-204 / 2026-01-03] 질문' 형태에서 조회 조건을 뽑는다.

    사용자가 화면에서 고르는 조건(라인·설비·기간)과 같은 자리에 넣는다.
    뽑지 못한 값은 비워 둔다 — 그 경우 서버가 범위 부족으로 거절하는지가 곧 평가 대상이다.
    """
    m = _TAG_RE.match(text.strip())
    tag, question = (m.group("tag"), m.group("question")) if m else ("", text)
    line = re.search(r"LINE-[A-Z]", tag)
    equipments = re.findall(r"EQ-\d{3}", tag)
    dates = _DATE_RE.findall(tag)
    req: dict = {"message": text.strip()}
    if len(equipments) == 1:      # 'EQ-037 + EQ-043'처럼 둘이면 설비를 못 정하고 라인만 준다
        req["equipment_id"] = equipments[0]
    # 화면에서 설비를 고르면 라인은 설비 마스터가 채운다. 입력 문장의 라인 표기가 마스터와 어긋난
    # 평가 항목이 있어(예: 22번) 그대로 넘기면 내용 평가 전에 '라인 불일치'로 거절된다.
    # 설비가 정해지지 않았을 때만 라인을 조건으로 준다.
    elif line:
        req["line_id"] = line.group(0)
    if dates:
        req["date_from"] = dates[0]
        req["date_to"] = dates[1] if len(dates) > 1 else dates[0]
    return req


# ─────────────────────────────────────────────
# 분석기 호출 — 서버(POST /report)와 같은 경로: 요청 검증 → 범위 확정 → 리포트 생성
# ─────────────────────────────────────────────
async def analyze(fields: dict, *, session: str, images: list[str] | None = None, use_scope: bool = True) -> dict:
    """{"status": "ok"|"rejected"|"infra_error", ...} 를 돌려준다. 예외를 밖으로 내보내지 않는다."""
    import backend.main as app_main
    from fastapi import HTTPException
    from pydantic import ValidationError

    try:
        request = app_main.ReportRequest(**fields, **({"images": images} if images else {}))
    except ValidationError as exc:
        msg = "; ".join(e["msg"] for e in exc.errors())
        return {"status": "rejected", "http": 422, "reason": msg}

    try:
        if use_scope:
            line_id, equipment_id = await app_main._resolve_request_scope(request)
        else:  # 요청의 라인·설비를 그대로 쓴다 (score_multimodal.py와 같은 조건)
            line_id, equipment_id = request.line_id, request.equipment_id
    except HTTPException as exc:
        return {"status": "rejected", "http": exc.status_code, "reason": str(exc.detail)}
    except Exception as exc:  # DB·마스터 조회 실패 등
        return {"status": "infra_error", "reason": f"{type(exc).__name__}: {exc}"[:300]}

    for attempt in range(3):
        try:
            report = await generate_report(
                line_id=line_id, equipment_id=equipment_id,
                date_from=request.date_from, date_to=request.date_to,
                session_id=None, images=request.images, message=request.message,
                report_id=f"eval-{int(time.time() * 1000)}",
                trace_session_id=session, user_id="eval-runner",
            )
            return {"status": "ok", "report": report.model_dump(), "scope": [line_id, equipment_id]}
        except AnalysisInfrastructureError as exc:
            info = llm.last_infra_error() or {}
            if info.get("permanent") or attempt == 2:
                return {"status": "infra_error", "reason": str(exc)[:300], "info": info}
            await asyncio.sleep(20 * (attempt + 1))  # 402(in-flight 예약)은 기다리면 풀린다
    return {"status": "infra_error", "reason": "재시도 초과"}


# ─────────────────────────────────────────────
# 텍스트 채점
# ─────────────────────────────────────────────
JUDGE_PROMPT = """당신은 제조 설비 다운타임 원인 분석 서비스의 평가자입니다.
서비스가 낸 [실제 출력]을 [기대 답]과 비교해 채점하세요.

[질문]
{question}

[기대 답]
{expected}

[정답 근거 (평가셋 작성자의 메모)]
{why}

[실제 출력]
{output}

채점 기준
1) match (핵심 판정이 기대 답과 맞는가)
   - 1   : 기대 답의 핵심(원인·심각도·'판정 불가'/'거절'/'확인 필요' 등)과 일치한다.
   - 0.5 : 일부만 맞거나, 핵심은 맞지만 중요한 부분이 빠졌다.
   - 0   : 핵심이 어긋난다(다른 원인·심각도, 거절해야 하는데 분석했거나 그 반대).
   - 기대 답이 '정답 미확정'이면 정해진 결론과 비교하지 말고,
     "판단 근거를 제시했고 잠정 판단·사람의 확인이 필요하다고 밝혔는가"로 1 / 0.5 / 0을 준다.
   - 실제 출력이 status=rejected이면(요청이 서버에서 거절됨) 기대 답이 거절·오류 안내를
     요구할 때만 1, 그 외에는 0이다.
2) honesty (근거가 부족한 곳을 확정처럼 단정하지 않았는가)
   - 1 : 원인을 확정·단정하지 않고, 필요한 곳에 '잠정'·'현장 확인 필요'를 밝혔다.
   - 0 : 기대 답이 확정을 피하라고 했는데 원인을 확정했거나, 근거가 없는데 확신하는 어조로 결론냈다.
   - ⚠️ 당신은 데이터베이스를 볼 수 없습니다. 출력이 인용한 정비 기록·로그 ID가 기대 답에 없다는 이유로
     "지어냈다"고 판단하지 마세요(실제 기록일 수 있습니다). 기록의 존재 여부는 별도 규칙이 검사합니다.
     여기서는 **단정의 강도**만 보세요.

JSON 한 덩어리만 출력하세요. 다른 말은 쓰지 마세요.
{{"match": 0 | 0.5 | 1, "honesty": 0 | 1, "reason": "한두 문장"}}"""


def _judge_call(prompt: str) -> dict:
    key = os.getenv("MESTORY_LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("MESTORY_JUDGE_MODEL", DEFAULT_JUDGE)
    last = None
    for attempt in range(3):
        try:
            r = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": model, "temperature": 0, "max_tokens": 600,
                    "provider": {"zdr": True},
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=90,
            )
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"]
            m = re.search(r"\{.*\}", text, re.DOTALL)
            return json.loads(m.group(0))
        except Exception as exc:  # 네트워크·JSON 오류는 재시도
            last = exc
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"판정 실패: {last!r}")


def _short_output(output: dict) -> str:
    if output.get("status") != "ok":
        return json.dumps(output, ensure_ascii=False)[:1500]
    rep = output["report"]
    slim = {
        "status": "ok",
        "causes": [{k: c.get(k) for k in ("error_code", "description", "severity", "is_confirmed")}
                   for c in rep.get("causes", [])],
        "unclassified_count": rep.get("unclassified_count"),
        "confidence_note": rep.get("confidence_note"),
        "recommended_action": rep.get("recommended_action"),
    }
    return json.dumps(slim, ensure_ascii=False)[:3500]


_ID_RE = re.compile(r"(?<![A-Za-z0-9])(?:MT-\d{5}|LOG-\d{6})(?!\d)")
_known_ids: set[str] | None = None


def known_record_ids() -> set[str]:
    """실제 데이터에 있는 정비·정지 기록 ID. 판정 모델은 DB를 못 보므로 존재 여부는 규칙으로 잰다."""
    global _known_ids
    if _known_ids is None:
        from mcp_server.tools.data_loader import load_downtime_logs, load_maintenance

        _known_ids = (set(load_maintenance()["maintenance_id"].astype(str))
                      | set(load_downtime_logs()["log_id"].astype(str)))
    return _known_ids


def id_grounding(report: dict) -> Evaluation:
    blob = json.dumps(report, ensure_ascii=False)
    cited = set(_ID_RE.findall(blob))
    invented = sorted(cited - known_record_ids())
    return Evaluation(name="id_grounding", value=0.0 if invented else 1.0,
                      comment=f"없는 기록 ID 인용: {invented}" if invented else f"인용한 기록 ID {len(cited)}개 모두 실존")


def text_evaluator(*, input, output, expected_output, metadata=None, **kwargs):
    metadata = metadata or {}
    if output.get("status") == "infra_error":
        # 모델이 틀린 것이 아니라 측정을 못 한 것이다 — 점수를 매기지 않는다.
        return [Evaluation(name="contract", value=0.0, comment=f"인프라 오류: {output.get('reason')}")]

    report = output.get("report") or {}
    fell_back = "자동 분석 실패" in (report.get("confidence_note") or "")
    contract = Evaluation(name="contract", value=0.0 if fell_back else 1.0,
                          comment="폴백" if fell_back else "정상 처리")

    question = input if isinstance(input, str) else json.dumps(input, ensure_ascii=False)
    verdict = _judge_call(JUDGE_PROMPT.format(
        question=question, expected=expected_output, why=metadata.get("why", "(없음)"),
        output=_short_output(output),
    ))
    return [
        contract,
        id_grounding(report),
        Evaluation(name="judge_match", value=float(verdict["match"]), comment=str(verdict.get("reason", ""))),
        Evaluation(name="judge_honesty", value=float(verdict["honesty"]), comment=str(verdict.get("reason", ""))),
    ]


# ─────────────────────────────────────────────
# 텍스트 Dataset — evals/dataset.jsonl에서 만든다 (없을 때만). ensure_mm_dataset()과 같은 모양
# ─────────────────────────────────────────────
def load_text_cases() -> list[dict]:
    """텍스트 평가셋을 읽는다. **읽기만 한다** — 내용은 강경희 님 담당이다."""
    return [json.loads(line) for line in TEXT_DATASET_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]


def text_fingerprint(cases: list[dict]) -> str:
    """평가셋 내용의 지문(sha256 16진수).

    파일 바이트가 아니라 **읽어 들인 내용**으로 잰다. Windows 작업 폴더는 CRLF, 저장소는 LF라
    바이트로 재면 같은 평가셋인데 PC마다 지문이 달라진다. 키 순서도 고정해서 잰다.
    """
    canonical = json.dumps(cases, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def default_text_dataset_name(cases: list[dict]) -> str:
    """Dataset 이름 = 건수 + 지문 앞 8자리. 평가셋이 바뀌면 이름이 바뀌어 새 Dataset이 생긴다."""
    return f"mestory-text-{len(cases)}-{text_fingerprint(cases)[:8]}"


def ensure_text_dataset(lf, name: str) -> None:
    try:
        lf.get_dataset(name)
        return
    except Exception:
        pass
    cases = load_text_cases()
    fp8 = text_fingerprint(cases)[:8]
    lf.create_dataset(name=name, description=f"MESTORY 텍스트 평가셋 {len(cases)}건 "
                                              f"(evals/dataset.jsonl에서 생성, 지문 {fp8})")
    for c in cases:
        # 항목 id는 프로젝트 전체에서 하나여야 하고 다른 Dataset에 다시 쓸 수 없다(Langfuse SDK 설명).
        # 그래서 지문을 넣는다 — 평가셋이 바뀌어 새 Dataset을 만들 때 id가 겹치지 않는다.
        # 회차끼리 짝을 맞추는 키는 id가 아니라 metadata의 case_id(평가셋의 id)다.
        lf.create_dataset_item(
            dataset_name=name, id=f"mestory-text-{fp8}-{c['id']}", input=c["input"],
            expected_output=c["expected"],
            metadata={"case_id": c["id"], "note": c.get("note"), "why": c.get("why")},
        )
    print(f"텍스트 Dataset '{name}' 생성 ({len(cases)}건)")


# ─────────────────────────────────────────────
# 멀티모달 — 채점은 score_multimodal.py와 같은 규칙을 그대로 쓴다
# ─────────────────────────────────────────────
def ensure_mm_dataset(lf, name: str) -> None:
    try:
        lf.get_dataset(name)
        return
    except Exception:
        pass
    lf.create_dataset(name=name, description="MESTORY 멀티모달 평가셋 10건 (evals/dataset_multimodal.jsonl에서 생성)")
    for line in MM_DATASET_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        c = json.loads(line)
        lf.create_dataset_item(
            dataset_name=name, id=f"mestory-mm-{c['id']}", input=c["input"], expected_output=c["expected"],
            metadata={"case_id": c["id"], "image": c["image"], "request": c["request"], "checks": c["checks"],
                      "note": c["note"], "why": c["why"]},
        )
    print(f"멀티모달 Dataset '{name}' 생성 (10건)")


def make_mm_evaluator():
    import score_multimodal as sm

    codes = sm.known_codes()

    def evaluator(*, input, output, expected_output, metadata=None, **kwargs):
        if output.get("status") != "ok":
            return [Evaluation(name="contract", value=0.0, comment=f"측정 불가: {output.get('reason')}")]
        from backend.services.llm import DowntimeReport

        report = DowntimeReport(**output["report"])
        case = {"id": metadata["case_id"], "image": metadata["image"], "note": metadata["note"],
                "checks": metadata["checks"]}
        scored = sm.score_case(case, report, codes)
        comment = "; ".join(scored["failed"]) or "전부 통과"
        return [Evaluation(name=axis, value=float(v), comment=comment) for axis, v in scored["axes"].items()]

    return evaluator


# ─────────────────────────────────────────────
# 실행
# ─────────────────────────────────────────────
def summarize(result) -> dict:
    per_axis: dict[str, list[float]] = {}
    items = []
    for ir in result.item_results:
        # case_id = 평가셋의 id. 회차끼리 짝을 맞추는 키다(Langfuse 항목 id는 Dataset마다 달라 못 쓴다).
        # 2026-09-22 전 Dataset의 항목에는 없어서 None이 된다 → 비교할 때 item_id로 대신한다.
        metadata = getattr(ir.item, "metadata", None)
        metadata = metadata if isinstance(metadata, dict) else {}   # Langfuse는 metadata에 아무 값이나 허용한다
        row = {"item_id": getattr(ir.item, "id", None), "case_id": metadata.get("case_id"),
               "scores": {}, "comments": {}}
        for ev in ir.evaluations or []:
            per_axis.setdefault(ev.name, []).append(float(ev.value))
            row["scores"][ev.name] = float(ev.value)
            row["comments"][ev.name] = ev.comment
        out = ir.output if isinstance(ir.output, dict) else {}
        row["status"] = out.get("status")
        items.append(row)
    return {"mean": {k: round(statistics.mean(v), 3) for k, v in per_axis.items()},
            "n": {k: len(v) for k, v in per_axis.items()}, "items": items}


def run_one(lf, *, kind: str, dataset_name: str, tag: str, limit: int | None, concurrency: int):
    dataset = lf.get_dataset(dataset_name)
    items = list(dataset.items)
    if limit:
        items = items[:limit]
    print(f"\n[{kind}] Dataset '{dataset_name}' · {len(items)}건 · 회차 '{tag}'")

    if kind == "text":
        async def task(*, item, **kwargs):
            fields = parse_text_input(item.input if isinstance(item.input, str) else json.dumps(item.input))
            return await analyze(fields, session=f"eval-{tag}")

        evaluators = [text_evaluator]
    else:
        import score_multimodal as sm

        async def task(*, item, **kwargs):
            md = item.metadata or {}
            return await analyze(dict(md["request"]), session=f"eval-{tag}-mm", images=[sm.data_url(md["image"])],
                                 use_scope=False)

        evaluators = [make_mm_evaluator()]

    result = lf.run_experiment(
        name=f"mestory-{kind}-eval", run_name=f"{tag}-{kind}", description=f"{kind} 평가 회차 {tag}",
        data=items, task=task, evaluators=evaluators, max_concurrency=concurrency,
        metadata={"generator": llm.resolve_model_name(kind == "mm"),
                  "judge": os.getenv("MESTORY_JUDGE_MODEL", DEFAULT_JUDGE) if kind == "text" else "rule-based"},
    )
    summary = summarize(result)
    print(f"  평균: {summary['mean']}   (건수 {summary['n']})")
    for row in summary["items"]:
        low = {k: v for k, v in row["scores"].items() if v < 1}
        if low or row["status"] != "ok":
            print(f"   - {row['item_id']}: status={row['status']} 낮은 축={low}")
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tag", required=True, help="회차 이름 (예: before, after)")
    ap.add_argument("--only", choices=["text", "mm", "both"], default="both")
    ap.add_argument("--limit", type=int, help="항목 수 제한 (시험 실행용)")
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--text-dataset", default=None,
                    help=f"기본값: evals/dataset.jsonl에서 만든 mestory-text-<건수>-<지문>. "
                         f"옛 회차를 재현할 때만 지정 (예: {LEGACY_TEXT_DATASET})")
    ap.add_argument("--mm-dataset", default=DEFAULT_MM_DATASET)
    args = ap.parse_args()

    if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
        raise SystemExit("LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY가 없습니다")
    lf = get_client()

    out = {"tag": args.tag, "when": datetime.now().isoformat(timespec="seconds"),
           "generator": llm.get_model_name(), "judge": os.getenv("MESTORY_JUDGE_MODEL", DEFAULT_JUDGE)}
    if args.only in ("text", "both"):
        cases = load_text_cases()
        default_name = default_text_dataset_name(cases)
        text_dataset = args.text_dataset or default_name
        ensure_text_dataset(lf, text_dataset)
        # --compare가 '같은 평가셋에서 잰 회차인가'를 가르는 근거. 이름에 지문이 든 기본 Dataset일 때만 적는다
        # (이름을 직접 지정하면 그 Dataset이 지금의 jsonl과 같은 내용인지 보장할 수 없다).
        out["text_dataset"] = text_dataset
        out["text_dataset_fingerprint"] = text_fingerprint(cases) if text_dataset == default_name else None
        out["text"] = run_one(lf, kind="text", dataset_name=text_dataset, tag=args.tag,
                              limit=args.limit, concurrency=args.concurrency)
    if args.only in ("mm", "both"):
        ensure_mm_dataset(lf, args.mm_dataset)
        out["mm"] = run_one(lf, kind="mm", dataset_name=args.mm_dataset, tag=args.tag,
                            limit=args.limit, concurrency=args.concurrency)
    lf.flush()

    RUNS.mkdir(exist_ok=True)
    path = RUNS / f"langfuse_{args.tag}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n결과 저장: {path.relative_to(REPO_ROOT)}  (Langfuse → Datasets → Experiments에서도 볼 수 있음)")


if __name__ == "__main__":
    main()
