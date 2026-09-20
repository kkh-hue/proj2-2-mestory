"""알림센터 표기·숨김 규칙 — DB 없이 순수 함수만 검증한다."""

from datetime import date

import pytest

from backend.db import _already_analyzed, _period_covers, _scope_name

pytestmark = pytest.mark.no_data


def test_설비_알림은_이름_형식():
    assert _scope_name("LINE-E", "EQ-057", "컨베이어") == "E라인 · 컨베이어 · EQ-057"


def test_라인_단위는_라인_전체_설비():
    assert _scope_name("LINE-B", "LINE-B 전체 설비", None) == "B라인 전체 설비"


@pytest.mark.parametrize("period,day,expected", [
    ("전체 ~ 전체", date(2026, 9, 1), True),
    ("2026-09-14 ~ 2026-09-20", date(2026, 9, 14), True),
    ("2026-09-14 ~ 2026-09-20", date(2026, 9, 13), False),
    ("2026-09-14 ~ 2026-09-20", date(2026, 9, 21), False),
    ("전체 ~ 2026-09-10", date(2026, 9, 11), False),
])
def test_리포트_기간이_그_날을_포함하는지(period, day, expected):
    assert _period_covers(period, day) is expected


def test_같은_설비_리포트가_기간을_덮으면_이미_분석됨():
    scopes = [("LINE-E", "EQ-057", "2026-09-14 ~ 2026-09-20")]
    assert _already_analyzed("LINE-E", "EQ-057", date(2026, 9, 15), scopes)
    assert not _already_analyzed("LINE-E", "EQ-048", date(2026, 9, 15), scopes)
    assert not _already_analyzed("LINE-E", "EQ-057", date(2026, 9, 25), scopes)


def test_라인_전체_리포트는_그_라인의_설비를_모두_덮는다():
    scopes = [("LINE-B", "LINE-B 전체 설비", "2026-09-14 ~ 2026-09-20")]
    assert _already_analyzed("LINE-B", "EQ-021", date(2026, 9, 16), scopes)
    assert not _already_analyzed("LINE-A", "EQ-001", date(2026, 9, 16), scopes)
