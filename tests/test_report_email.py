"""리포트 메일 발송 — docs/specs/report-email.md

지금은 (1) is_allowed_recipient 만 검증한다. (2) 본문 만들기와 (3) 실제 발송은 다음 단계.
"""

import pytest

from backend.report_email import is_allowed_recipient

# 이 파일의 시험은 CSV/DB 데이터가 없어도 돌아간다 (conftest.py의 no_data 표시).
pytestmark = pytest.mark.no_data


@pytest.fixture
def allowlist(monkeypatch):
    """허용 목록 환경변수를 시험마다 원하는 값으로 바꾼다.

    monkeypatch를 쓰는 이유: 시험이 끝나면 pytest가 원래 값으로 되돌려 준다.
    직접 os.environ을 고치면 다음 시험까지 값이 남아 결과가 서로 엉킨다.
    """
    def _set(value: str | None):
        if value is None:
            monkeypatch.delenv("REPORT_EMAIL_ALLOWLIST", raising=False)
        else:
            monkeypatch.setenv("REPORT_EMAIL_ALLOWLIST", value)
    return _set


# ─────────────────────────────────────────────
# 허용되는 경우
# ─────────────────────────────────────────────
def test_목록에_있는_주소는_허용한다(allowlist):
    allowlist("ok@example.com,team@example.com")

    assert is_allowed_recipient("ok@example.com") is True
    assert is_allowed_recipient("team@example.com") is True


@pytest.mark.parametrize("given", [
    "OK@EXAMPLE.COM",      # 전부 대문자
    "Ok@Example.Com",      # 섞임
    "  ok@example.com  ",  # 앞뒤 공백
    "\tok@example.com\n",  # 탭·줄바꿈
])
def test_대소문자와_공백이_달라도_같은_주소로_본다(allowlist, given):
    # 메일 주소는 대소문자를 구분하지 않는 것이 관례다.
    allowlist("ok@example.com")

    assert is_allowed_recipient(given) is True


def test_목록_쪽에_공백이나_빈_항목이_있어도_동작한다(allowlist):
    # 사람이 손으로 적는 값이라 쉼표가 겹치거나 공백이 섞이기 쉽다.
    allowlist("  ok@example.com ,, TEAM@example.com ,")

    assert is_allowed_recipient("ok@example.com") is True
    assert is_allowed_recipient("team@example.com") is True


# ─────────────────────────────────────────────
# 거절하는 경우
# ─────────────────────────────────────────────
def test_목록에_없는_주소는_거절한다(allowlist):
    allowlist("ok@example.com")

    assert is_allowed_recipient("stranger@evil.com") is False


def test_부분만_일치하는_주소는_거절한다(allowlist):
    # "ok@example.com.evil.com" 같은 주소가 통과하면 안 된다 — 완전히 같아야 한다.
    allowlist("ok@example.com")

    assert is_allowed_recipient("ok@example.com.evil.com") is False
    assert is_allowed_recipient("notok@example.com") is False
    assert is_allowed_recipient("ok@example.co") is False


# ─────────────────────────────────────────────
# AC-05 · 목록이 비어 있으면 아무도 받지 못한다
# ─────────────────────────────────────────────
@pytest.mark.parametrize("empty_value", [None, "", "   ", ",", " , , "])
def test_AC05_허용목록이_비면_모두_거절한다(allowlist, empty_value):
    # 설정을 빠뜨렸을 때 "일단 통과"가 되면, 조용히 아무에게나 메일이 나간다.
    # 기본값은 반드시 막힘이어야 한다.
    allowlist(empty_value)

    assert is_allowed_recipient("ok@example.com") is False
    assert is_allowed_recipient("anyone@anywhere.com") is False


def test_빈_주소는_거절한다(allowlist):
    allowlist("ok@example.com")

    assert is_allowed_recipient("") is False
    assert is_allowed_recipient("   ") is False
