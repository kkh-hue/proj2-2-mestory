"""알림센터 표기·상태 일관성 규칙 — DB 없이 검증한다."""

import asyncio
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import pytest

import backend.db as db
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


class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    async def fetchall(self):
        return self.rows


class _Connection:
    def __init__(self, query_rows):
        self.query_rows = iter(query_rows)
        self.queries = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def execute(self, *args):
        self.queries.append(args)
        return _Cursor(next(self.query_rows))


def test_설비현황_상태로_다운타임_알림을_결정하고_분석완료는_유지한다(monkeypatch):
    """정상 설비의 과거 이벤트는 숨기고, 설비현황 상태로만 다운타임 톤을 정한다."""
    day = date(2026, 9, 20)
    start = datetime(2026, 9, 19, 9, 0)
    report_created = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
    downtime_rows = [
        ("LOG-NORMAL", "EQ-001", "LINE-A", "E-101", start, False, False, True, "프레스", "LINE-A", "정상 설비 이벤트"),
        ("LOG-WARNING", "EQ-002", "LINE-LOG", "E-102", start, False, False, True, "프레스", "LINE-MASTER", "주의 설비 이벤트"),
        ("LOG-STOPPED", "EQ-003", "LINE-A", "E-103", start, True, True, True, "프레스", "LINE-A", "정지 설비 이벤트"),
        ("LOG-FUTURE-END", "EQ-003", "LINE-A", "E-105", start, False, True, True, "프레스", "LINE-A", "종료 예정 정지 이벤트"),
        ("LOG-STOPPED-CLOSED", "EQ-003", "LINE-A", "E-104", start, False, False, True, "프레스", "LINE-A", "이미 끝난 이벤트"),
    ]
    report_rows = [
        ("report-1", "EQ-001", "LINE-A", "조치 확인", report_created, True, "프레스", "LINE-A"),
    ]
    connection = _Connection([downtime_rows, report_rows, []])
    monkeypatch.setattr(db, "_connect", AsyncMock(return_value=connection))
    monkeypatch.setattr(
        db,
        "list_equipment_status",
        AsyncMock(return_value=[
            {"equipment_id": "EQ-001", "status": "정상"},
            {"equipment_id": "EQ-002", "status": "주의"},
            {"equipment_id": "EQ-003", "status": "정지"},
        ]),
    )

    alerts = asyncio.run(db.list_alerts(as_of=day))
    by_id = {alert["id"]: alert for alert in alerts}
    assert "d.end_time >= %s" in connection.queries[0][0]
    assert connection.queries[0][1][0].date() == day

    assert "downtime-LOG-NORMAL" not in by_id
    assert (by_id["downtime-LOG-WARNING"]["tone"], by_id["downtime-LOG-WARNING"]["tag"]) == ("warning", "주의")
    assert by_id["downtime-LOG-WARNING"]["line_id"] == "LINE-MASTER"
    assert "MASTER라인" in by_id["downtime-LOG-WARNING"]["title"]
    assert (by_id["downtime-LOG-STOPPED"]["tone"], by_id["downtime-LOG-STOPPED"]["tag"]) == ("critical", "긴급")
    assert "진행 중입니다" in by_id["downtime-LOG-STOPPED"]["description"]
    assert "진행 중입니다" in by_id["downtime-LOG-FUTURE-END"]["description"]
    # 설비가 정지여도 이미 끝난 행은 "진행 중"이 아니다 (태그는 설비 상태를 따른다)
    assert by_id["downtime-LOG-STOPPED-CLOSED"]["tag"] == "긴급"
    assert "있었습니다" in by_id["downtime-LOG-STOPPED-CLOSED"]["description"]
    assert (by_id["report-report-1"]["tone"], by_id["report-report-1"]["tag"]) == ("analysis", "분석 완료")


def test_정상_이벤트가_많아도_상태_필터링_뒤_limit을_적용한다(monkeypatch):
    day = date(2026, 9, 20)
    start = datetime(2026, 9, 19, 9, 0)
    normal_rows = [
        (f"LOG-NORMAL-{index}", f"EQ-NORMAL-{index}", "LINE-A", "E-101", start, False, False, True, "프레스", "LINE-A", "정상 설비 이벤트")
        for index in range(30)
    ]
    warning_row = ("LOG-WARNING", "EQ-WARNING", "LINE-A", "E-102", start, False, False, True, "프레스", "LINE-A", "주의 설비 이벤트")
    connection = _Connection([normal_rows + [warning_row], [], []])
    monkeypatch.setattr(db, "_connect", AsyncMock(return_value=connection))
    monkeypatch.setattr(
        db,
        "list_equipment_status",
        AsyncMock(return_value=[
            *({"equipment_id": f"EQ-NORMAL-{index}", "status": "정상"} for index in range(30)),
            {"equipment_id": "EQ-WARNING", "status": "주의"},
        ]),
    )

    alerts = asyncio.run(db.list_alerts(limit=1, as_of=day))

    assert [alert["id"] for alert in alerts] == ["downtime-LOG-WARNING"]
    assert "limit" not in connection.queries[0][0].lower()


def test_마스터에_없는_설비의_다운타임_알림은_숨긴다(monkeypatch):
    day = date(2026, 9, 20)
    start = datetime(2026, 9, 19, 9, 0)
    rows = [
        ("LOG-GHOST", "EQ-058", "LINE-E", "E-102", start, False, False, True, None, None, "마스터에 없는 설비"),
        ("LOG-STOPPED", "EQ-003", "LINE-A", "E-103", start, True, True, True, "프레스", "LINE-A", "정지 설비 이벤트"),
    ]
    connection = _Connection([rows, [], []])
    monkeypatch.setattr(db, "_connect", AsyncMock(return_value=connection))
    monkeypatch.setattr(
        db, "list_equipment_status", AsyncMock(return_value=[{"equipment_id": "EQ-003", "status": "정지"}])
    )

    alerts = asyncio.run(db.list_alerts(as_of=day))

    assert [alert["id"] for alert in alerts] == ["downtime-LOG-STOPPED"]


def test_기준_시각은_오늘이면_지금_지난_날짜면_그날_끝():
    today = db._today_kst()
    now_cutoff = db._cutoff(None)
    assert now_cutoff.tzinfo is None
    assert abs((datetime.now(db._KST).replace(tzinfo=None) - now_cutoff).total_seconds()) < 5
    assert abs((db._cutoff(today) - now_cutoff).total_seconds()) < 5
    past = date(2026, 3, 15)
    assert db._cutoff(past) == datetime(2026, 3, 16, 0, 0)
    assert db._aware(db._cutoff(past)).utcoffset().total_seconds() == 9 * 3600


def test_대시보드_전일_대비는_같은_경과_시간끼리_비교한다(monkeypatch):
    day = date(2026, 9, 15)  # 지난 날짜: 경과가 하루라 어제 전체와 비교
    seen = {}

    class _Conn:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def execute(self, sql, params=()):
            seen.setdefault("params", []).append(params)
            raise RuntimeError("stop after first query")

    monkeypatch.setattr(db, "_connect", AsyncMock(return_value=_Conn()))
    with pytest.raises(db.DatabaseUnavailableError):
        asyncio.run(db.get_dashboard_summary(day))
    kpi_params = seen["params"][0]
    assert kpi_params[0:2] == (day, datetime(2026, 9, 16))
    assert kpi_params[2:4] == (date(2026, 9, 14), datetime(2026, 9, 15))
