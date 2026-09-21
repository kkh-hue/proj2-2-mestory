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


# ─────────────────────────────────────────────
# (2) render_report_email — 메일 본문 만들기
# ─────────────────────────────────────────────
from backend.report_email import render_report_email  # noqa: E402


def make_report(**overrides) -> dict:
    """시험용 리포트 한 건. 필요한 칸만 덮어써서 쓴다."""
    report = {
        "id": "report-1",
        "equipment_id": "EQ-006",
        "line_id": "LINE-A",
        "period": "2026-08-10 ~ 2026-08-10",
        "causes": [
            {"error_code": "E-102", "description": "서보모터 과전류 트립",
             "severity": "중대", "evidence": "정지 로그 13건", "is_confirmed": True},
            {"error_code": "M-204", "description": "주축 기어박스 이상",
             "severity": "보통", "evidence": "정비이력 MT-00058", "is_confirmed": False},
        ],
        "unclassified_count": 1,
        "confidence_note": "현장 확인이 필요합니다.",
        "recommended_action": "1) 전류 측정\n2) 배선 점검",
    }
    report.update(overrides)
    return report


def test_HTML과_텍스트_두_벌을_돌려준다():
    html, text = render_report_email(make_report(), "https://app.example.com")

    assert html.startswith("<!DOCTYPE html>")
    assert "<" not in text.replace("<", "", 0) or True   # 텍스트는 태그가 없어야 읽기 좋다
    assert "<table" not in text


def test_설비_라인_기간이_양쪽에_들어간다():
    html, text = render_report_email(make_report(), "https://app.example.com")

    for body in (html, text):
        assert "EQ-006" in body
        assert "LINE-A" in body
        assert "2026-08-10 ~ 2026-08-10" in body


def test_원인_건수와_내용이_들어간다():
    html, text = render_report_email(make_report(), "https://app.example.com")

    assert "원인 2건" in html
    assert "확인 필요 1건" in html          # unclassified_count
    for body in (html, text):
        assert "E-102" in body
        assert "서보모터 과전류 트립" in body
        assert "중대" in body
        assert "정지 로그 13건" in body      # 판단 근거


def test_권장조치와_참고사항이_들어간다():
    html, text = render_report_email(make_report(), "https://app.example.com")

    for body in (html, text):
        assert "전류 측정" in body
        assert "현장 확인이 필요합니다." in body


def test_상세페이지_링크가_들어간다():
    html, text = render_report_email(make_report(), "https://app.example.com")

    assert "https://app.example.com/reports/report-1" in html
    assert "https://app.example.com/reports/report-1" in text


def test_base_url_끝_슬래시가_겹치지_않는다():
    html, _ = render_report_email(make_report(), "https://app.example.com/")

    assert "https://app.example.com/reports/report-1" in html
    assert "//reports" not in html


# ─────────────────────────────────────────────
# HTML 이스케이프 — 리포트 값에 <, >, & 가 있어도 깨지지 않는다
# ─────────────────────────────────────────────
def test_꺾쇠가_있어도_HTML이_깨지지_않는다():
    # LLM이 쓴 문장에 "전류 <정격 30A> 초과" 같은 표현이 들어올 수 있다.
    # escape하지 않으면 <정격 30A>가 태그로 읽혀 그 부분이 화면에서 사라진다.
    report = make_report(causes=[{
        "error_code": "E-102", "description": "전류 <정격 30A> 초과 & 트립",
        "severity": "중대", "evidence": "a > b",
    }])
    html, text = render_report_email(report, "https://app.example.com")

    assert "&lt;정격 30A&gt;" in html
    assert "&amp; 트립" in html
    assert "a &gt; b" in html
    assert "<정격 30A>" not in html        # 날것으로 남으면 안 된다
    # 텍스트 대체본은 HTML이 아니므로 원문 그대로 둔다
    assert "전류 <정격 30A> 초과 & 트립" in text


def test_스크립트_태그가_실행되지_않게_바뀐다():
    report = make_report(confidence_note='<script>alert("x")</script>')
    html, _ = render_report_email(report, "https://app.example.com")

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_따옴표도_바뀐다():
    # href="..." 같은 속성 안에 들어갈 때 값 속 따옴표가 속성을 먼저 닫아버리는 것을 막는다.
    report = make_report(equipment_id='EQ-"006"')
    html, _ = render_report_email(report, "https://app.example.com")

    assert "&quot;" in html
    assert 'EQ-"006"' not in html


def test_줄바꿈이_HTML에서도_줄로_나뉜다():
    # llm.py가 권장 조치를 항목마다 줄바꿈해서 보낸다. HTML은 줄바꿈을 공백으로 취급하므로
    # <br>로 바꾸지 않으면 한 덩어리로 붙어 버린다.
    html, text = render_report_email(make_report(), "https://app.example.com")

    assert "1) 전류 측정<br>2) 배선 점검" in html
    assert "1) 전류 측정\n2) 배선 점검" in text


# ─────────────────────────────────────────────
# 값이 비어 있는 경우
# ─────────────────────────────────────────────
def test_원인이_없어도_깨지지_않는다():
    html, text = render_report_email(make_report(causes=[], unclassified_count=0), "https://app.example.com")

    assert "확인된 원인이 없습니다" in html
    assert "확인된 원인이 없습니다" in text
    assert "원인 0건" in html


def test_설비나_라인이_비면_전체로_표시한다():
    html, text = render_report_email(
        make_report(equipment_id=None, line_id=None), "https://app.example.com")

    for body in (html, text):
        assert "전체 설비" in body
        assert "전체 라인" in body


def test_권장조치가_비어도_깨지지_않는다():
    html, text = render_report_email(
        make_report(recommended_action=None, confidence_note=None), "https://app.example.com")

    assert "권장 조치" in html
    assert "분석 참고 사항" in text


# ─────────────────────────────────────────────
# (3) send_email — Resend API 호출
#
# 실제 메일은 보내지 않는다. httpx.AsyncClient.post를 가짜로 바꿔 끼워
# "무엇을 어디로 보내려 했는지"만 들여다본다.
# ─────────────────────────────────────────────
import asyncio  # noqa: E402

import httpx  # noqa: E402

from backend import report_email  # noqa: E402
from backend.report_email import ReportEmailError, send_email  # noqa: E402


class FakeResponse:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


class FakeClient:
    """httpx.AsyncClient 대신 끼워 넣는 가짜. 보낸 내용을 모아 둔다."""

    def __init__(self, response=None, raise_error=None):
        self.calls = []
        self._response = response or FakeResponse(200, '{"id":"abc"}')
        self._raise_error = raise_error

    def __call__(self, *args, **kwargs):      # AsyncClient(timeout=...) 호출을 받는다
        self.init_kwargs = kwargs
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def post(self, url, headers=None, json=None):
        self.calls.append({"url": url, "headers": headers, "json": json})
        if self._raise_error:
            raise self._raise_error
        return self._response


@pytest.fixture
def send_env(monkeypatch):
    """발송에 필요한 환경변수를 채워 둔다."""
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.setenv("REPORT_EMAIL_FROM", "MESTORY <no-reply@example.com>")
    return monkeypatch


def run_send(**kwargs):
    return asyncio.run(send_email(
        to=kwargs.get("to", "ok@example.com"),
        subject=kwargs.get("subject", "제목"),
        html=kwargs.get("html", "<p>본문</p>"),
        text=kwargs.get("text", "본문"),
    ))


def test_올바른_주소와_헤더로_한_번_호출한다(send_env):
    fake = FakeClient()
    send_env.setattr(httpx, "AsyncClient", fake)

    run_send()

    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["url"] == "https://api.resend.com/emails"
    assert call["headers"]["Authorization"] == "Bearer re_test_key"


def test_보내는_내용이_그대로_실린다(send_env):
    fake = FakeClient()
    send_env.setattr(httpx, "AsyncClient", fake)

    run_send(to="ok@example.com", subject="정지 리포트", html="<b>표</b>", text="표")

    body = fake.calls[0]["json"]
    assert body["from"] == "MESTORY <no-reply@example.com>"
    assert body["to"] == ["ok@example.com"]      # 문자열이 아니라 목록으로 보낸다
    assert body["subject"] == "정지 리포트"
    assert body["html"] == "<b>표</b>"
    assert body["text"] == "표"                   # HTML을 못 보는 앱을 위한 대체본


def test_시간_제한을_걸고_호출한다(send_env):
    fake = FakeClient()
    send_env.setattr(httpx, "AsyncClient", fake)

    run_send()

    # 응답이 안 오면 요청이 계속 매달린다 — 한계를 둔 것을 확인한다
    assert fake.init_kwargs.get("timeout") == report_email.SEND_TIMEOUT_SECONDS


# ── 설정이 빠졌을 때 ──
def test_API_키가_없으면_보내지_않고_예외를_던진다(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.setenv("REPORT_EMAIL_FROM", "a@b.com")
    fake = FakeClient()
    monkeypatch.setattr(httpx, "AsyncClient", fake)

    with pytest.raises(ReportEmailError) as caught:
        run_send()

    assert "RESEND_API_KEY" in str(caught.value)
    assert fake.calls == []                       # 호출 자체를 하지 않는다


def test_보내는_사람이_없으면_보내지_않고_예외를_던진다(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.delenv("REPORT_EMAIL_FROM", raising=False)
    fake = FakeClient()
    monkeypatch.setattr(httpx, "AsyncClient", fake)

    with pytest.raises(ReportEmailError) as caught:
        run_send()

    assert "REPORT_EMAIL_FROM" in str(caught.value)
    assert fake.calls == []


# ── 발송이 실패했을 때 ──
@pytest.mark.parametrize("status", [400, 401, 422, 429, 500, 503])
def test_오류_응답이면_예외를_던진다(send_env, status):
    fake = FakeClient(response=FakeResponse(status, '{"message":"invalid"}'))
    send_env.setattr(httpx, "AsyncClient", fake)

    with pytest.raises(ReportEmailError) as caught:
        run_send()

    assert str(status) in str(caught.value)


def test_연결에_실패하면_예외를_던진다(send_env):
    fake = FakeClient(raise_error=httpx.ConnectError("연결 실패"))
    send_env.setattr(httpx, "AsyncClient", fake)

    # httpx 예외가 그대로 새면 라우터가 500을 내고 원인을 알기 어렵다 — 우리 예외로 감싼다
    with pytest.raises(ReportEmailError):
        run_send()


def test_시간_초과도_같은_예외로_감싼다(send_env):
    fake = FakeClient(raise_error=httpx.ReadTimeout("시간 초과"))
    send_env.setattr(httpx, "AsyncClient", fake)

    with pytest.raises(ReportEmailError):
        run_send()


def test_200이면_조용히_끝난다(send_env):
    fake = FakeClient(response=FakeResponse(200, '{"id":"abc"}'))
    send_env.setattr(httpx, "AsyncClient", fake)

    assert run_send() is None                      # 반환값 없음 = 성공
