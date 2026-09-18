"""평가용 HMI 알람 화면 이미지를 만든다 (멀티모달 평가셋 재료).

왜 이미지를 직접 만드나
  실제 공장 HMI 사진이 우리에게 없다. 인터넷 사진은 라이선스도 문제지만,
  더 큰 문제는 거기 적힌 설비ID·에러코드가 우리 데이터와 아무 관계가 없어서
  MCP 조회가 이어지지 않는다는 것이다.
  우리가 만들면 ① 정답을 처음부터 알고 있어 채점이 깔끔하고
  ② 채점자도 이 스크립트를 돌려 같은 이미지를 재현할 수 있다.

핵심 원칙: 이미지에 적는 값은 전부 **실제 데이터에서 읽어온다.**
  하드코딩한 가짜 값을 적으면, 그 이미지로 조회해도 기록이 안 나온다.
  그래서 log_id로 진짜 행을 찾아 그 행의 값을 그대로 그린다.

실행 (저장소 최상위 폴더에서)
    python scripts/make_hmi_images.py            # evals/images/ 에 생성
    python scripts/make_hmi_images.py --list      # 만들 목록만 보기
    python scripts/make_hmi_images.py --out /tmp/x  # 다른 폴더에 생성

만들어지는 것
    evals/images/*.png       이미지 10장
    evals/images/labels.json 각 이미지의 정답(무엇이 적혀 있는지) + 케이스 분류
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# 이 파일 위치: proj2-2/scripts/make_hmi_images.py → 한 칸 위가 저장소 최상위
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from mcp_server.tools.data_loader import load_downtime_logs, load_error_codes  # noqa: E402

DEFAULT_OUT = REPO_ROOT / "evals" / "images"

# ─────────────────────────────────────────────
# 1단계 · 어떤 이미지를 만들지 정한다
#
# log_id = 실제 데이터의 행. 그 행의 값이 그대로 이미지에 적힌다.
# case   = 평가셋 분류 (가이드 9-3: 정상 + 경계 + 실패 유도)
# expect = 이 이미지로 기대하는 동작 (채점 기준)
# ─────────────────────────────────────────────
PLAN = [
    {
        "name": "normal_e102",
        "log_id": "LOG-011583",
        "case": "정상",
        "variant": "clean",
        "expect": "visual_findings에 EQ-006과 E-102가 담긴다",
    },
    {
        "name": "normal_m204_long",
        "log_id": "LOG-014099",
        "case": "정상",
        "variant": "clean",
        "expect": "visual_findings에 EQ-015와 M-204가 담기고, 720분 장기 정지가 반영된다",
    },
    {
        "name": "boundary_unregistered_code",
        "log_id": "LOG-014093",
        "case": "경계",
        "variant": "clean",
        "expect": "X-999는 사전에 없는 코드 → severity '판정 불가', is_confirmed false",
    },
    {
        "name": "boundary_planned_stop",
        "log_id": "LOG-011563",
        "case": "경계",
        "variant": "clean",
        "expect": "ETC-602는 계획 정지 → 원인 목록에서 제외된다",
    },
    {
        "name": "boundary_empty_code",
        "log_id": "LOG-014095",
        "case": "경계",
        "variant": "clean",
        "expect": "에러코드 칸이 비어 있다 → '판정 불가'. 코드를 지어내지 않는다",
    },
    # ── 실패 유도: 같은 정상 화면을 일부러 읽기 어렵게 만든다 ──
    {
        "name": "fail_lowres",
        "log_id": "LOG-011583",
        "case": "실패유도",
        "variant": "lowres",
        "expect": "읽히면 정상 처리, 안 읽히면 visual_findings 빈 목록 + confidence_note에 식별 불가",
    },
    {
        "name": "fail_blur",
        "log_id": "LOG-011583",
        "case": "실패유도",
        "variant": "blur",
        "expect": "흐려서 못 읽으면 빈 목록. 데이터에 없는 코드를 지어내면 실패",
    },
    {
        "name": "fail_tilted",
        "log_id": "LOG-011583",
        "case": "실패유도",
        "variant": "tilted",
        "expect": "회전 때문에 라벨과 값의 줄이 어긋나 보인다(ERROR CODE 옆에 LINE-A가 오는 식). 값이 한 열에 모여 있음을 보고 짝을 맞춰야 한다 → E-102를 LINE-A로 잘못 읽으면 실패",
    },
    {
        "name": "fail_glare",
        "log_id": "LOG-011583",
        "case": "실패유도",
        "variant": "glare",
        # 반사광으로 일부러 가린 항목. labels.json의 visible에서 빼야 채점이 맞는다.
        "hidden": ["error_code"],
        "expect": "반사광이 ERROR CODE 값만 덮는다. 설비ID·시각은 읽히고 코드는 못 읽는 상태 → 코드를 지어내면 실패. visual_findings에 코드가 없어야 한다",
    },
    {
        "name": "fail_irrelevant",
        "log_id": None,  # 데이터와 무관한 이미지
        "case": "실패유도",
        "variant": "irrelevant",
        "expect": "설비와 무관한 이미지 → visual_findings에 '요청과 무관' 1건. 원인은 텍스트·MCP 근거로만",
    },
]

# ─────────────────────────────────────────────
# 2단계 · 글꼴 찾기
#
# 에러코드·설비ID·시각은 전부 영문·숫자라서 어떤 글꼴에서도 읽힌다.
# 한글(에러 설명·작업자 메모)은 한글 글꼴이 있어야 안 깨진다.
# 없으면 한글 줄을 생략한다 — 핵심 정보는 그래도 다 남는다.
# ─────────────────────────────────────────────
MONO_FONTS = [
    r"C:\Windows\Fonts\consolab.ttf",          # Windows
    r"C:\Windows\Fonts\arialbd.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",   # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
]
KOREAN_FONTS = [
    r"C:\Windows\Fonts\malgunbd.ttf",          # 맑은 고딕 Bold
    r"C:\Windows\Fonts\malgun.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
]


def _first_existing(paths: list[str]) -> str | None:
    for p in paths:
        if Path(p).exists():
            return p
    return None


MONO_PATH = _first_existing(MONO_FONTS)
KOREAN_PATH = _first_existing(KOREAN_FONTS)


def mono(size: int):
    """영문·숫자용 글꼴. HMI 패널 느낌을 내려고 고정폭을 쓴다."""
    return ImageFont.truetype(MONO_PATH, size) if MONO_PATH else ImageFont.load_default()


def korean(size: int):
    """한글용 글꼴. 없으면 None을 돌려주고, 부르는 쪽에서 한글 줄을 생략한다."""
    return ImageFont.truetype(KOREAN_PATH, size) if KOREAN_PATH else None


# ─────────────────────────────────────────────
# 3단계 · 정상 화면 한 장 그리기
# ─────────────────────────────────────────────
W, H = 1000, 640
BG = (17, 21, 28)          # 어두운 패널 배경
ALARM = (176, 32, 38)      # 알람 띠 빨강
LABEL = (146, 157, 173)    # 항목 이름 회색
VALUE = (234, 239, 247)    # 값 흰색
DANGER = (255, 96, 96)     # 에러코드 강조 빨강


def draw_panel(row: dict, code_info: dict | None) -> Image.Image:
    """설비 알람 화면 한 장을 그린다. row는 실제 정지 로그 한 줄이다."""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # 상단 알람 띠
    d.rectangle([0, 0, W, 96], fill=ALARM)
    d.text((32, 28), "EQUIPMENT ALARM", font=mono(42), fill=(255, 255, 255))
    d.text((W - 210, 38), row["log_id"], font=mono(24), fill=(255, 220, 220))

    # 본문 — 이름/값 표. 값은 전부 실제 데이터에서 온다.
    #   에러코드가 빈 문자열인 행이 실제로 있다(LOG-014095). 그때는 화면에도 비워 둔다.
    #   "없음" 같은 글자를 대신 넣으면 LLM이 그걸 코드로 읽을 수 있다.
    code = str(row["error_code"]).strip()
    rows = [
        ("EQUIPMENT", str(row["equipment_id"]), VALUE),
        ("LINE", str(row["line_id"]), VALUE),
        ("ERROR CODE", code if code else "", DANGER),
        ("STATUS", "STOPPED", VALUE),
        ("START", str(row["start_time"]), VALUE),
        ("DOWNTIME", f'{row["downtime_min"]} min', VALUE),
    ]
    y = 140
    for label, value, color in rows:
        d.text((40, y), label, font=mono(26), fill=LABEL)
        d.text((360, y), value, font=mono(32), fill=color)
        y += 62

    # 하단 안내 — 한글. 글꼴이 없으면 이 줄만 건너뛴다.
    d.rectangle([0, H - 96, W, H], fill=(28, 34, 45))
    kf = korean(22)
    if kf is not None:
        # 에러코드 사전의 설명과 작업자 메모를 실제 값으로 넣는다.
        # code_info가 None인 경우 = 사전에 없는 코드(X-999)거나 코드가 비어 있는 행.
        desc = (code_info.get("description") if code_info else "") or "사전에 없는 코드 — 현장 확인 필요"
        note = str(row.get("operator_note", "") or "").strip()
        d.text((32, H - 84), f"설명: {desc}", font=kf, fill=(196, 205, 219))
        if note:
            d.text((32, H - 50), f"메모: {note}", font=kf, fill=(158, 168, 184))
    else:
        d.text((32, H - 70), "PRESS RESET AFTER CHECKING", font=mono(22), fill=(158, 168, 184))

    return img


# ─────────────────────────────────────────────
# 4단계 · 실패 유도용으로 망가뜨리기
#
# 전부 '결정적'이다 (무작위 없음) → 다시 돌리면 똑같은 이미지가 나온다.
# 채점자가 재현할 수 있어야 하기 때문이다.
# ─────────────────────────────────────────────
def make_lowres(img: Image.Image) -> Image.Image:
    """작게 줄였다가 다시 키운다 = 화질이 무너진 휴대폰 사진 흉내."""
    small = img.resize((W // 5, H // 5), Image.BILINEAR)
    return small.resize((W, H), Image.NEAREST)


def make_blur(img: Image.Image) -> Image.Image:
    """초점이 안 맞은 사진."""
    return img.filter(ImageFilter.GaussianBlur(radius=4.5))


def make_tilted(img: Image.Image) -> Image.Image:
    """비스듬히 서서 찍은 사진. 빈 자리는 어두운 배경으로 채운다."""
    return img.rotate(-11, resample=Image.BICUBIC, expand=True, fillcolor=(10, 12, 16))


def make_glare(img: Image.Image) -> Image.Image:
    """모니터에 빛이 반사돼 **에러코드 값이 하얗게 날아간** 사진.

    여기가 이 이미지의 핵심이다. 반사광을 화면 전체에 약하게 깔면 값이 다 읽혀서
    실패 유도가 되지 않는다(처음에 그렇게 만들었다가 눈으로 확인하고 고쳤다).
    그래서 ERROR CODE 값 한 칸만 완전히 지운다.
      → 설비ID·시각은 읽히는데 코드만 못 읽는 상태가 되고,
        "못 읽은 코드를 지어내는가"를 정확히 시험할 수 있다.
    ERROR CODE 값의 위치는 draw_panel의 좌표(x 360부터, 세 번째 줄 y≈264)에서 왔다.
    """
    out = img.convert("RGB")
    overlay = Image.new("L", (W, H), 0)
    od = ImageDraw.Draw(overlay)
    # ① 현장감을 위한 약한 대각선 반사광 (읽기를 방해하지 않는 정도)
    od.polygon([(120, 0), (330, 0), (690, H), (470, H)], fill=110)
    # ② ERROR CODE 값 칸을 완전히 덮는다.
    #    블러를 먹이면 테두리가 약해져 글자가 비쳐 보이므로, 글자 위치보다
    #    넉넉하게(왼쪽 270부터) 잡고 블러를 약하게 준다.
    od.ellipse([248, 232, 736, 332], fill=255)
    # ③ 하단 한글 설명줄도 덮는다.
    #    왜 필요한가: 설명("서보모터 과전류 트립")은 사전에서 E-102의 설명이라,
    #    코드를 가려도 이 줄을 읽으면 코드를 되짚을 수 있다. 정답이 새어나가면
    #    "못 읽은 코드를 지어내는가"를 시험할 수 없다.
    od.rectangle([0, H - 132, W, H], fill=255)
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=16))
    white = Image.new("RGB", (W, H), (255, 255, 255))
    return Image.composite(white, out, overlay)


def make_irrelevant() -> Image.Image:
    """설비와 아무 상관 없는 이미지 (EC-08 확인용).
    사람·상표가 없는 단순 도형으로 만든다."""
    img = Image.new("RGB", (W, H), (236, 240, 245))
    d = ImageDraw.Draw(img)
    d.ellipse([160, 120, 520, 480], fill=(120, 170, 210))
    d.rectangle([540, 220, 860, 420], fill=(232, 196, 120))
    d.line([100, 560, 900, 560], fill=(150, 160, 175), width=8)
    return img


VARIANTS = {
    "clean": lambda img: img,
    "lowres": make_lowres,
    "blur": make_blur,
    "tilted": make_tilted,
    "glare": make_glare,
}


# ─────────────────────────────────────────────
# 5단계 · 실행
# ─────────────────────────────────────────────
def find_row(log: "object", log_id: str) -> dict:
    """log_id로 실제 행 하나를 찾는다. 없으면 바로 멈춘다 —
    조용히 넘어가면 데이터와 안 맞는 이미지가 만들어진다."""
    hit = log[log["log_id"] == log_id]
    if len(hit) == 0:
        raise SystemExit(f"데이터에 {log_id} 행이 없습니다. PLAN을 데이터에 맞게 고치세요.")
    return hit.iloc[0].to_dict()


def main() -> None:
    parser = argparse.ArgumentParser(description="평가용 HMI 화면 이미지 생성")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="생성 폴더 (기본 evals/images)")
    parser.add_argument("--list", action="store_true", help="만들 목록만 보고 끝낸다")
    args = parser.parse_args()

    if args.list:
        for item in PLAN:
            print(f'  {item["case"]:5s} {item["name"]:28s} {item["log_id"] or "-":12s} {item["variant"]}')
        return

    print(f"영문 글꼴 : {MONO_PATH or '기본 글꼴(작게 나올 수 있음)'}")
    print(f"한글 글꼴 : {KOREAN_PATH or '없음 — 한글 줄은 생략됩니다'}")

    log = load_downtime_logs()
    codes = load_error_codes()
    # pandas Series를 그대로 담으면 `if code_info:` 판정이 모호해져 에러가 난다
    # (ValueError: The truth value of a Series is ambiguous) → dict로 바꿔 담는다.
    code_map = {str(r["error_code"]): r.to_dict() for _, r in codes.iterrows()}

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    labels = []
    for item in PLAN:
        name = item["name"]
        path = out_dir / f"{name}.png"

        if item["variant"] == "irrelevant":
            make_irrelevant().save(path)
            labels.append({
                "file": path.name,
                "case": item["case"],
                "variant": item["variant"],
                "log_id": None,
                "visible": {},          # 읽어낼 값이 없다
                "hidden": {},
                "expect": item["expect"],
            })
            print(f'  ✅ {name:28s} (데이터 무관 이미지)')
            continue

        row = find_row(log, item["log_id"])
        code = str(row["error_code"]).strip()
        panel = draw_panel(row, code_map.get(code))
        VARIANTS[item["variant"]](panel).save(path)

        # 정답 = 이미지에서 **실제로 읽을 수 있는** 값. 채점은 이것과 비교한다.
        # 일부러 가린 항목(glare의 error_code 등)은 visible에서 빼고 hidden에 적는다.
        #   왜 중요한가: 가려 놓고 정답에 적어두면, 모델이 못 읽는 게 맞는데도
        #   틀렸다고 채점된다. 반대로 지어낸 값이 정답과 맞으면 통과해 버린다.
        hidden = item.get("hidden", [])
        all_values = {
            "equipment_id": str(row["equipment_id"]),
            "line_id": str(row["line_id"]),
            "error_code": code,            # 빈 코드 행은 빈 문자열
            "start_time": str(row["start_time"]),
            "downtime_min": float(row["downtime_min"]),
        }
        labels.append({
            "file": path.name,
            "case": item["case"],
            "variant": item["variant"],
            "log_id": row["log_id"],
            "visible": {k: v for k, v in all_values.items() if k not in hidden},
            "hidden": {k: all_values[k] for k in hidden},   # 가린 값(참고용, 채점에 쓰지 않음)
            "expect": item["expect"],
        })
        print(f'  ✅ {name:28s} {row["equipment_id"]} / {code or "(빈 코드)"} / {item["variant"]}')

    labels_path = out_dir / "labels.json"
    labels_path.write_text(
        json.dumps(
            {
                "note": "visible = 이미지에서 실제로 읽을 수 있는 값(= 채점 정답). hidden = 일부러 가린 값으로, 채점에 쓰지 않는다(모델이 이 값을 말하면 추측한 것). 모든 값은 data/downtime_log.csv의 실제 행에서 가져왔다.",
                "generated_by": "scripts/make_hmi_images.py",
                "images": labels,
                "mismatch_case": {
                    "note": "AC-08(이미지 설비ID ≠ 입력 설비ID)은 새 이미지가 필요 없다. "
                            "normal_e102.png(EQ-006)를 equipment_id=EQ-010으로 조회하면 된다. "
                            "기대: 리포트의 equipment_id는 EQ-010(사용자 입력), 불일치는 confidence_note에.",
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    total = sum(1 for _ in labels)
    counts: dict[str, int] = {}
    for item in labels:
        counts[item["case"]] = counts.get(item["case"], 0) + 1
    print(f"\n  이미지 {total}장 + labels.json → {out_dir}")
    print("  구성:", " / ".join(f"{k} {v}건" for k, v in counts.items()))


if __name__ == "__main__":
    main()
