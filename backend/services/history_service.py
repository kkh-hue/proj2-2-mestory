from typing import Any

from backend.models.auth import HistoryCreateRequest
from backend.services.auth_db import AuthDatabase


class HistoryService:
    def __init__(self, database: AuthDatabase | None = None):
        self.database = database or AuthDatabase()

    def save_for_user(self, user_id: str, request: HistoryCreateRequest) -> dict[str, Any]:
        return self.database.save_history(user_id, request.model_dump())

    def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        return self.database.list_history(user_id)

    def get_for_user(self, user_id: str, history_id: str) -> dict[str, Any] | None:
        # user_id가 WHERE 조건에 포함되어 다른 사용자의 history_id 접근을 차단한다.
        return self.database.get_history(user_id, history_id)
