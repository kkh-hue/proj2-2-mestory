"""DB 저장 실패가 성공 응답으로 숨겨지지 않는지 검증한다."""

import asyncio
import pytest

from backend import db
from backend.services.llm import DowntimeReport


class FailingConnection:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def execute(self, *_args):
        raise RuntimeError("insert failed")


async def failing_connect():
    return FailingConnection()


def test_save_report_failure_raises_database_error(monkeypatch):
    monkeypatch.setattr(db, "_connect", failing_connect)
    report = DowntimeReport(
        equipment_id="EQ-001", line_id="LINE-A", period="전체 ~ 전체", causes=[],
        unclassified_count=0, confidence_note="", recommended_action="",
    )

    with pytest.raises(db.DatabaseUnavailableError):
        asyncio.run(db.save_report("report-1", report, "session-1"))


@pytest.mark.parametrize("role", ["user", "assistant"])
def test_save_message_failure_raises_database_error(monkeypatch, role):
    monkeypatch.setattr(db, "_connect", failing_connect)

    with pytest.raises(db.DatabaseUnavailableError):
        asyncio.run(db.save_message("session-1", role, "content", report_id="report-1"))
