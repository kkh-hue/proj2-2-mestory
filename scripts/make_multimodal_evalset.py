"""멀티모달 평가셋(evals/dataset_multimodal.jsonl)을 만든다.

왜 손으로 안 쓰고 생성하나
  평가셋의 정답은 이미지에 실제로 적힌 값이어야 한다.
  손으로 적으면 이미지를 고쳤을 때 평가셋이 조용히 어긋난다
  (실제로 fail_glare에서 한 번 겪었다 — 가린 값을 정답에 적어두면 채점이 뒤집힌다).
  그래서 evals/images/labels.json에서 파생시킨다.

기존 evals/dataset.jsonl은 건드리지 않는다
  그쪽은 텍스트 케이스 30건이고 담당자가 다르다. 이미지 케이스는 파일을 나눠
  충돌을 피하고, 채점 스크립트가 둘을 따로 다룬다.

실행
    python scripts/make_multimodal_evalset.py
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
IMAGES = REPO_ROOT / "evals" / "images"
OUT = REPO_ROOT / "evals" / "dataset_multimodal.jsonl"

# 조회 조건 — 이미지에 적힌 날짜를 그대로 쓴다.
# 이미지의 값으로 조회했을 때 실제 기록이 나와야 리포트가 만들어진다.
WHEN = {
    "normal_e102.png": ("2026-08-10", "2026-08-10"),
    "normal_m204_long.png": ("2026-11-02", "2026-11-02"),
    "boundary_unregistered_code.png": ("2026-08-10", "2026-08-10"),
    "boundary_planned_stop.png": ("2026-08-10", "2026-08-10"),
    "boundary_empty_code.png": ("2026-08-12", "2026-08-12"),
}


def build() -> list[dict]:
    labels = {
        item["file"]: item
        for item in json.loads((IMAGES / "labels.json").read_text(encoding="utf-8"))["images"]
    }
    cases: list[dict] = []

    def add(case_id, file, note, why, request, checks, expected):
        cases.append({
            "id": case_id,
            "image": file,
            "request": request,          # generate_report에 넘길 조건
            "input": (f"[{request.get('line_id') or '전체'} / {request.get('equipment_id') or '전체'} / "
                      f"{request.get('date_from')}~{request.get('date_to')}] "
                      f"첨부한 설비 화면({file})을 함께 보고 원인 분석 리포트를 만들어 주세요."),
            "expected": expected,
            "note": note,
            "why": why,
            "checks": checks,            # 규칙 기반 채점 근거
        })

    # ── 정상 2건 : 읽을 수 있는 화면 → 값이 그대로 담겨야 한다 ──
    for file, case_id in (("normal_e102.png", "MM-01"), ("normal_m204_long.png", "MM-02")):
        v = labels[file]["visible"]
        eq, code = v["equipment_id"], v["error_code"]
        d_from, d_to = WHEN[file]
        add(
            case_id, file,
            "정상 케이스 — 이미지에서 설비ID·에러코드 추출",
            f"labels.json의 visible 값. 이미지는 downtime_log의 {labels[file]['log_id']} 행을 그린 것이라 "
            f"같은 조건으로 조회하면 실제 기록이 나온다.",
            {"equipment_id": eq, "line_id": v["line_id"], "date_from": d_from, "date_to": d_to},
            {
                "used_image": True,
                "visual_must_include": [eq, code],
                "visual_must_not_include": [],
                "severity_must_include": None,
                "equipment_id_equals": eq,
            },
            f"visual_findings에 {eq}와 {code}가 담긴다. used_image=true.",
        )

    # ── 경계 1 : 사전에 없는 코드 → 읽기는 하되 '판정 불가' ──
    f = "boundary_unregistered_code.png"
    v = labels[f]["visible"]
    add(
        "MM-03", f,
        "경계 케이스 — 사전에 없는 코드(X-999)",
        "SKILL.md: 미등록 코드는 근거가 없으므로 '판정 불가' + is_confirmed=false. "
        "화면에는 또렷이 보이므로 읽는 것 자체는 성공해야 한다.",
        {"equipment_id": v["equipment_id"], "line_id": v["line_id"],
         "date_from": WHEN[f][0], "date_to": WHEN[f][1]},
        {
            "used_image": True,
            "visual_must_include": [v["equipment_id"], v["error_code"]],
            "visual_must_not_include": [],
            "severity_must_include": "판정 불가",
            "equipment_id_equals": v["equipment_id"],
        },
        "visual_findings에 X-999가 담기고, causes의 severity에 '판정 불가'가 있어야 한다.",
    )

    # ── 경계 2 : 계획 정지 → 원인 목록에서 빠진다 ──
    f = "boundary_planned_stop.png"
    v = labels[f]["visible"]
    add(
        "MM-04", f,
        "경계 케이스 — 계획 정지(ETC-602)",
        "SKILL.md·docs/specs/downtime-logs.md: 계획 정지는 총계에는 들어가지만 원인 집계에서 제외한다. "
        "이미지에서 코드를 읽는 것과, 그걸 원인으로 올리지 않는 것은 별개다.",
        {"equipment_id": v["equipment_id"], "line_id": v["line_id"],
         "date_from": WHEN[f][0], "date_to": WHEN[f][1]},
        {
            "used_image": True,
            "visual_must_include": [v["equipment_id"], v["error_code"]],
            "visual_must_not_include": [],
            "severity_must_include": None,
            "cause_codes_must_not_include": [v["error_code"]],   # 원인으로 올리면 안 된다
            "equipment_id_equals": v["equipment_id"],
        },
        "visual_findings에 ETC-602는 담기되, causes의 error_code에는 없어야 한다(계획 정지).",
    )

    # ── 경계 3 : 에러코드 칸이 비어 있음 → 코드를 지어내면 안 된다 ──
    f = "boundary_empty_code.png"
    v = labels[f]["visible"]
    add(
        "MM-05", f,
        "경계 케이스 — 에러코드 칸이 비어 있음",
        "실제 데이터에 빈 코드 행이 있다(LOG-014095). 화면에도 비워 그렸다. "
        "SKILL.md: 빈 에러코드는 '판정 불가'.",
        {"equipment_id": v["equipment_id"], "line_id": v["line_id"],
         "date_from": WHEN[f][0], "date_to": WHEN[f][1]},
        {
            "used_image": True,
            "visual_must_include": [v["equipment_id"]],
            "visual_must_not_include": [],
            # 화면의 코드 칸이 비어 있으므로, 사전에 있는 코드를 말해도 지어낸 것이다.
            "visual_no_code_at_all": True,
            "severity_must_include": "판정 불가",
            "equipment_id_equals": v["equipment_id"],
        },
        "코드를 지어내지 않는다. severity에 '판정 불가'.",
    )

    # ── 실패 유도 1 : 반사광으로 코드만 가림 → 가린 값을 말하면 실패 ──
    f = "fail_glare.png"
    hidden = labels[f]["hidden"]["error_code"]
    v = labels[f]["visible"]
    add(
        "MM-06", f,
        "실패 유도 — 반사광으로 에러코드만 가림",
        f"이미지에서 {hidden}는 보이지 않는다(labels.json의 hidden). "
        f"MCP 조회 결과에는 {hidden}가 있으므로 causes에 나오는 것은 정상이지만, "
        f"'이미지에서 읽었다'는 뜻의 visual_findings에 넣으면 지어낸 것이다.",
        {"equipment_id": v["equipment_id"], "line_id": v["line_id"],
         "date_from": "2026-08-10", "date_to": "2026-08-10"},
        {
            "used_image": True,
            "visual_must_include": [v["equipment_id"]],     # 설비ID는 읽힌다
            "visual_must_not_include": [hidden],            # ★ 핵심 검사
            "severity_must_include": None,
            "equipment_id_equals": v["equipment_id"],
        },
        f"visual_findings에 {v['equipment_id']}는 있고 {hidden}는 없어야 한다.",
    )

    # ── 실패 유도 2 : 흐림 → 없는 코드를 만들어내면 실패 ──
    f = "fail_blur.png"
    v = labels[f]["visible"]
    add(
        "MM-07", f,
        "실패 유도 — 초점이 안 맞은 사진",
        "읽히면 정상 처리, 안 읽히면 빈 목록이면 정상. 실패 조건은 '사전에 없는 코드를 만들어내는 것'이다.",
        {"equipment_id": v["equipment_id"], "line_id": v["line_id"],
         "date_from": "2026-08-10", "date_to": "2026-08-10"},
        {
            "used_image": True,
            "visual_must_include": [],
            "visual_must_not_include": [],
            "visual_no_invented_code": True,
            "severity_must_include": None,
            "equipment_id_equals": v["equipment_id"],
        },
        "코드를 지어내지 않는다. 못 읽으면 빈 목록이어도 통과.",
    )

    # ── 실패 유도 3 : 기울임 → 라벨과 값의 짝을 맞춰야 한다 ──
    f = "fail_tilted.png"
    v = labels[f]["visible"]
    add(
        "MM-08", f,
        "실패 유도 — 기울어진 사진(라벨·값 어긋남)",
        "회전 때문에 ERROR CODE 옆에 LINE-A가 오는 식으로 줄이 어긋나 보인다. "
        "값이 한 열에 모여 있음을 보고 짝을 맞춰야 한다.",
        {"equipment_id": v["equipment_id"], "line_id": v["line_id"],
         "date_from": "2026-08-10", "date_to": "2026-08-10"},
        {
            "used_image": True,
            "visual_must_include": [],
            # 라인ID를 에러코드로 잘못 읽는 것이 이 케이스의 실패 모양이다
            "visual_no_wrong_pairing": {"error_code_must_not_be": v["line_id"]},
            "visual_no_invented_code": True,
            "severity_must_include": None,
            "equipment_id_equals": v["equipment_id"],
        },
        "LINE-A를 에러코드로 읽지 않는다. 코드를 지어내지 않는다.",
    )

    # ── 실패 유도 4 : 무관한 이미지 ──
    add(
        "MM-09", "fail_irrelevant.png",
        "실패 유도 — 설비와 무관한 이미지",
        "docs/specs/multimodal.md EC-08. 이미지에서 얻을 게 없으므로 "
        "원인은 텍스트·MCP 근거로만 판단해야 한다.",
        {"equipment_id": "EQ-006", "line_id": "LINE-A",
         "date_from": "2026-08-10", "date_to": "2026-08-10"},
        {
            "used_image": True,
            "visual_must_include": [],
            # 설비 화면이 아니므로 코드가 나올 수 없다.
            "visual_no_code_at_all": True,
            "severity_must_include": None,
            "equipment_id_equals": "EQ-006",
        },
        "이미지에서 설비 정보를 지어내지 않는다.",
    )

    # ── 실패 유도 5 : 이미지 설비ID ≠ 사용자 입력 ──
    f = "normal_e102.png"
    v = labels[f]["visible"]
    add(
        "MM-10", f,
        "실패 유도 — 이미지 설비ID와 입력 설비ID 불일치",
        "docs/specs/multimodal.md EC-07/AC-08. 사용자가 준 조건이 정답이고, "
        "불일치는 사람이 확인하도록 알려야 한다.",
        {"equipment_id": "EQ-010", "line_id": None,
         "date_from": "2026-08-10", "date_to": "2026-08-11"},
        {
            "used_image": True,
            "visual_must_include": [],
            "severity_must_include": None,
            "equipment_id_equals": "EQ-010",              # 이미지의 EQ-006이 아니다
            "note_must_mention_any": [v["equipment_id"], "불일치", "다르"],
        },
        "리포트의 equipment_id는 EQ-010. 불일치를 confidence_note 등에 남긴다.",
    )

    return cases


def main() -> None:
    cases = build()
    OUT.write_text(
        "\n".join(json.dumps(c, ensure_ascii=False) for c in cases) + "\n",
        encoding="utf-8",
    )
    from collections import Counter
    kinds = Counter(c["note"].split(" —")[0] for c in cases)
    print(f"  {OUT.relative_to(REPO_ROOT)} — {len(cases)}건")
    for k, n in kinds.items():
        print(f"    {k}: {n}건")


if __name__ == "__main__":
    main()
