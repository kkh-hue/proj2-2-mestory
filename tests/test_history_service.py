import pytest

pytest.importorskip("pydantic")

from backend.models.auth import HistoryCreateRequest
from backend.services.history_service import HistoryService


class FakeDatabase:
    def __init__(self):
        self.last_user_id = None

    def get_history(self, user_id, history_id):
        self.last_user_id = user_id
        return None


def test_history_lookup_scopes_by_authenticated_user():
    database = FakeDatabase()
    service = HistoryService(database)
    assert service.get_for_user("user-a", "history-b") is None
    assert database.last_user_id == "user-a"


def test_history_request_keeps_report_snapshot():
    request = HistoryCreateRequest(report_json={"period": "2026-01-01 ~ 2026-01-01", "causes": []})
    assert request.report_json["causes"] == []
