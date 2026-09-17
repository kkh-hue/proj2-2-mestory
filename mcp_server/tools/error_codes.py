"""
창구 ②: 에러코드 사전 조회  (팀 PRD F-02)

누가 부르나
  - LangChain 에이전트(AI)가 정지 기록의 에러코드 뜻을 알고 싶을 때 부른다.

하는 일
  - 에러코드 여러 개를 한 번에 받아서, 코드마다 사전 정보를 돌려준다.
    (코드 10개면 10번 부르지 않고 1번에 끝내서 빠르고 비용이 적다)
  - 사전에 없는 코드는 "없음(found: false)"을 분명하게 돌려준다.
    → AI가 모르는 코드의 원인을 지어내지 않게 하기 위해서 (SKILL.md 하지 말아야 할 것)
  - "보통 멈추는 시간" 범위("10~30")를 숫자(10, 30)로도 나눠서 준다.
    → SKILL.md 의 "정지시간이 범위 상한의 2배 이상이면 심각도 한 단계 상향" 규칙을
      AI나 백엔드가 쉽게 계산할 수 있게 하기 위해서

하지 않는 일
  - 심각도 최종 판단 (사전의 severity_hint 는 "참고값"으로 그대로 전달만 한다)
"""

# 같은 폴더의 파일들에서 필요한 것을 가져온다
from .data_loader import load_error_codes
from .downtime import PLANNED_STOP_CODES, UNKNOWN_CAUSE_CODES, _normalize_id

# 한 번에 조회할 수 있는 코드 수 상한 (사전 전체가 24개라 50이면 충분)
MAX_CODES = 50

# 사전에 없는 코드일 때 돌려줄 안내 문구
NOT_FOUND_MESSAGE = "에러코드 사전에 없는 코드입니다. 원인을 추정하지 말고 '판정 불가 — 현장 확인 필요'로 처리하세요."
EMPTY_CODE_MESSAGE = "에러코드가 비어 있습니다. '로그 기록 누락, 확인 필요'로 처리하세요."


# ─────────────────────────────────────────────
# 보조 함수: "10~30" 같은 범위 글자를 숫자 두 개로 나누기
# ─────────────────────────────────────────────
def _parse_range(text: str) -> tuple[float | None, float | None]:
    """'10~30' → (10.0, 30.0). 모양이 이상하면 (None, None)을 돌려준다.

    왜 None 을 돌려주나?
      사전 값이 잘못 적혀 있어도 창구 전체가 멈추면 안 되기 때문이다.
      숫자를 못 만들면 "모름(None)"으로 두고, 원래 글자는 그대로 함께 준다.
    """
    try:
        # "10~30".split("~") → ["10", "30"]
        low, high = text.split("~")
        return float(low), float(high)
    except (ValueError, AttributeError):
        # ValueError: "~"가 없거나 숫자가 아님 / AttributeError: 글자가 아닌 값이 들어옴
        return None, None


# ─────────────────────────────────────────────
# 메인 함수: 에러코드 사전 조회
# ─────────────────────────────────────────────
def lookup_error_codes(error_codes: list[str]) -> dict:
    """에러코드 목록을 받아 코드마다 사전 정보를 돌려준다.

    예: lookup_error_codes(["E-102", "x-999", ""])

    돌려주는 모양
      {
        "requested_count": 실제로 조회한 코드 수 (중복 제거 후),
        "found_count":     사전에서 찾은 코드 수,
        "not_found_codes": 사전에 없는 코드 목록,
        "results": [
          { "error_code": "E-102", "found": True,
            "category": "전기", "description": "서보모터 과전류 트립",
            "typical_cause": "...", "typical_duration_min_range": "10~30",
            "typical_min": 10.0, "typical_max": 30.0,
            "severity_hint": "보통",
            "is_planned_stop": False, "is_unknown_cause": False },
          { "error_code": "X-999", "found": False, "message": "사전에 없는 코드..." },
          ...
        ]
      }
    """

    # ── 1단계: 입력값 검사 ────────────────────
    # 글자 하나만 들어온 경우("E-102")도 목록으로 바꿔서 받아 준다 (AI 실수 대비)
    if isinstance(error_codes, str):
        error_codes = [error_codes]

    if not error_codes:
        raise ValueError("조회할 에러코드를 1개 이상 넣어 주세요. 예: [\"E-102\"]")

    # 표준 모양으로 맞추고(대문자·공백 제거), 중복은 빼되 들어온 순서는 유지한다.
    # dict.fromkeys(...) = 순서를 지키면서 중복을 없애는 짧은 방법
    # None(빈 코드)은 "" 로 바꿔서 "빈 코드"로 따로 안내한다
    cleaned = [(_normalize_id(code) if code is not None else None) or "" for code in error_codes]
    unique_codes = list(dict.fromkeys(cleaned))

    if len(unique_codes) > MAX_CODES:
        raise ValueError(f"한 번에 최대 {MAX_CODES}개까지 조회할 수 있습니다. (받은 개수: {len(unique_codes)})")

    # ── 2단계: 사전 읽기 ──────────────────────
    dictionary = load_error_codes()
    # 코드로 바로 찾을 수 있게 {코드: 한 줄 정보} 사전으로 바꾼다
    # set_index("error_code") = error_code 칸을 "찾는 열쇠"로 지정
    by_code = dictionary.set_index("error_code").to_dict("index")

    # ── 3단계: 코드마다 결과 만들기 ────────────
    results = []
    for code in unique_codes:

        # (1) 빈 코드
        if code == "":
            results.append({"error_code": "", "found": False, "message": EMPTY_CODE_MESSAGE})
            continue  # continue = 아래를 건너뛰고 다음 코드로

        # (2) 사전에 없는 코드
        info = by_code.get(code)  # 없으면 None
        if info is None:
            results.append({"error_code": code, "found": False, "message": NOT_FOUND_MESSAGE})
            continue

        # (3) 사전에 있는 코드
        typical_min, typical_max = _parse_range(info["typical_duration_min_range"])
        results.append({
            "error_code": code,
            "found": True,
            "category": info["category"],
            "description": info["description"],
            "typical_cause": info["typical_cause"],         # "흔한" 원인일 뿐, 확정 원인이 아님
            "typical_duration_min_range": info["typical_duration_min_range"],
            "typical_min": typical_min,
            "typical_max": typical_max,
            "severity_hint": info["severity_hint"],         # 참고용 심각도
            "is_planned_stop": code in PLANNED_STOP_CODES,  # 계획 정지인가 (ETC-602)
            "is_unknown_cause": code in UNKNOWN_CAUSE_CODES,  # 원인 미확인 코드인가 (ETC-604)
        })

    # ── 4단계: 결과 정리 ──────────────────────
    not_found = [r["error_code"] for r in results if not r["found"]]
    return {
        "requested_count": len(unique_codes),
        "found_count": len(unique_codes) - len(not_found),
        "not_found_codes": not_found,
        "results": results,
    }
