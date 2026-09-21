"""리포트 메일 발송 (docs/specs/report-email.md).

이 파일은 "메일을 만들고 보내는 일"만 한다. HTTP 라우팅은 main.py가 맡는다.
나눠 둔 이유: 시험에서 실제 메일을 보내지 않고 이 함수들만 가짜로 바꿔 끼우기 위해서다.
"""

from __future__ import annotations

import os

# 환경변수 이름을 상수로 둔다 — 오타가 나면 조용히 "설정 없음"으로 동작해 버리기 때문이다.
ALLOWLIST_ENV = "REPORT_EMAIL_ALLOWLIST"


def _normalize(address: str) -> str:
    """메일 주소를 비교하기 좋은 형태로 다듬는다 (앞뒤 공백 제거 + 소문자).

    소문자로 맞추는 이유: 메일 주소는 대소문자를 구분하지 않는 것이 관례다.
    'A@x.com'과 'a@x.com'은 같은 사람인데, 그냥 비교하면 다른 값이 된다.
    """
    return (address or "").strip().lower()


def is_allowed_recipient(to: str) -> bool:
    """이 주소로 메일을 보내도 되는지 판단한다.

    허용 목록은 REPORT_EMAIL_ALLOWLIST 환경변수에 쉼표로 구분해 적는다.
        REPORT_EMAIL_ALLOWLIST=a@example.com, b@example.com

    ⚠️ 목록이 없거나 비어 있으면 **모두 거절한다** (Spec AC-05).
    흔한 실수가 "설정이 없으면 일단 통과"로 짜는 것인데, 그러면 .env를 하나 빠뜨렸을 때
    조용히 아무에게나 메일이 나간다. 기본값은 안전한 쪽(막힘)이어야 한다.
    """
    raw = os.getenv(ALLOWLIST_ENV, "")

    # 쉼표로 자른 뒤 각 항목을 다듬고, 빈 항목은 버린다.
    # "a@x.com,,b@y.com"이나 끝에 쉼표가 붙은 값도 이 단계에서 정리된다.
    allowed = {_normalize(item) for item in raw.split(",") if item.strip()}

    if not allowed:
        return False

    # 입력 주소도 목록과 똑같은 방식으로 다듬어야 한다.
    # 한쪽만 소문자로 바꾸면 'A@x.com'이 목록에 있어도 막힌다.
    return _normalize(to) in allowed
