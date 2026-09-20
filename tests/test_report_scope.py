"""리포트 범위 확정 AC (docs/specs/report-scope.md) — DB·LLM 없이 순수 함수만 검증."""

import pytest

from backend.scope import ScopeError, resolve_scope

pytestmark = pytest.mark.no_data

LINES = {"EQ-057": "LINE-C", "EQ-012": "LINE-A", "EQ-001": "LINE-A"}


def test_ac01_질문_속_설비로_설비와_라인이_정해진다():
    assert resolve_scope("EQ-057 다운타임 원인 분석해줘", None, None, LINES, None) == ("LINE-C", "EQ-057")


def test_ac01_한글이_바로_붙어도_설비를_찾는다():
    assert resolve_scope("EQ-057컨베이어 원인은?", None, None, LINES, None) == ("LINE-C", "EQ-057")


def test_ac02_자릿수를_생략해도_정규화된다():
    assert resolve_scope("eq-57 왜 멈췄어?", None, None, LINES, None) == ("LINE-C", "EQ-057")


@pytest.mark.parametrize("message", ["LINE-B 정지 원인은?", "B라인 정지 원인은?", "b 라인 정지 원인은?"])
def test_ac03_라인만_말하면_라인_범위(message):
    assert resolve_scope(message, None, None, LINES, None) == ("LINE-B", None)


def test_ac04_범위가_없는_후속_질문은_세션_범위를_따른다():
    assert resolve_scope("그럼 언제 점검했어?", None, None, LINES, ("LINE-C", "EQ-057")) == ("LINE-C", "EQ-057")


def test_ac05_후속_질문이_다른_설비를_말하면_그_설비가_우선():
    assert resolve_scope("EQ-012는 어때?", None, None, LINES, ("LINE-C", "EQ-057")) == ("LINE-A", "EQ-012")


def test_ec04_요청에서_고른_조건이_질문보다_우선():
    with pytest.raises(ScopeError):
        resolve_scope("EQ-012 봐줘", None, "EQ-001", LINES, None)


def test_ec05_설비와_요청_라인이_불일치하면_거부():
    with pytest.raises(ScopeError):
        resolve_scope("EQ-057 분석", "LINE-A", "EQ-057", LINES, None)


def test_ec06_존재하지_않는_설비는_거부():
    with pytest.raises(ScopeError):
        resolve_scope("", "LINE-A", "EQ-999", LINES, None)


def test_ec07_질문의_라인과_설비_마스터가_불일치하면_거부():
    with pytest.raises(ScopeError):
        resolve_scope("LINE-A EQ-057 분석", None, "EQ-057", LINES, None)


def test_ac06_어디에도_범위가_없으면_에러():
    with pytest.raises(ScopeError, match="설비"):
        resolve_scope("원인 분석해줘", None, None, LINES, None)


def test_ac07_마스터에_없는_설비는_에러():
    with pytest.raises(ScopeError, match="EQ-999"):
        resolve_scope("EQ-999 분석해줘", None, None, LINES, None)


def test_ec07_마스터를_못_읽으면_명시된_값만으로_진행():
    assert resolve_scope("EQ-057 분석", None, None, None, None) == (None, "EQ-057")


TYPES = {"EQ-057": "컨베이어", "EQ-012": "컨베이어", "EQ-001": "사출성형기", "EQ-070": "컨베이어"}
LINES2 = {"EQ-057": "LINE-E", "EQ-012": "LINE-A", "EQ-001": "LINE-A", "EQ-070": "LINE-A"}


def test_ac09_라인_안에_그_종류가_1대면_그_설비():
    assert resolve_scope("E라인 컨베이어 분석해줘", None, None, LINES2, None, TYPES) == ("LINE-E", "EQ-057")


def test_ac09_여러_대면_후보를_알려_준다():
    with pytest.raises(ScopeError, match="EQ-012.*EQ-070"):
        resolve_scope("A라인 컨베이어 분석해줘", None, None, LINES2, None, TYPES)


def test_ec08_라인_없이_종류만_있어도_여러_대면_안내():
    with pytest.raises(ScopeError, match="3대"):
        resolve_scope("컨베이어 원인은?", None, None, LINES2, None, TYPES)


def test_ec09_세션_범위가_있으면_종류_이름은_무시하고_세션을_따른다():
    assert resolve_scope("그 컨베이어 언제 점검했어?", None, None, LINES2, ("LINE-E", "EQ-057"), TYPES) == ("LINE-E", "EQ-057")


def test_ec08_종류_이름이_없으면_추론하지_않는다():
    with pytest.raises(ScopeError, match="설비"):
        resolve_scope("원인 분석해줘", None, None, LINES2, None, TYPES)
