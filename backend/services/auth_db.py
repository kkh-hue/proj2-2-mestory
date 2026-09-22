"""auth/history 전용 DB 접근 계층. 기존 MCP 데이터 loader나 schema를 수정하지 않는다."""

from datetime import datetime
import json
from typing import Any
from uuid import uuid4

from mcp_server.tools.data_loader import _get_database_url


class AuthDatabase:
    def _connect(self):
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("psycopg[binary] 패키지가 필요합니다.") from exc
        return psycopg.connect(_get_database_url())

    def create_user(self, email: str, password_hash: str) -> dict[str, Any]:
        user_id = str(uuid4())
        with self._connect() as conn:
            row = conn.execute(
                "insert into users (user_id, email, password_hash) values (%s, %s, %s) returning user_id, email, created_at",
                (user_id, email, password_hash),
            ).fetchone()
        return {"user_id": str(row[0]), "email": row[1], "created_at": row[2]}

    def find_user_by_email(self, email: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("select user_id, email, password_hash, created_at from users where email = %s", (email,)).fetchone()
        return None if row is None else {"user_id": str(row[0]), "email": row[1], "password_hash": row[2], "created_at": row[3]}

    def find_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("select user_id, email, created_at from users where user_id = %s", (user_id,)).fetchone()
        return None if row is None else {"user_id": str(row[0]), "email": row[1], "created_at": row[2]}

    def save_history(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        history_id = str(uuid4())
        with self._connect() as conn:
            row = conn.execute(
                """insert into analysis_history (history_id, user_id, date_from, date_to, line_id, equipment_id, report_json)
                   values (%s, %s, %s, %s, %s, %s, %s::jsonb)
                   returning history_id, analyzed_at""",
                (history_id, user_id, payload.get("date_from"), payload.get("date_to"), payload.get("line_id"), payload.get("equipment_id"), json.dumps(payload["report_json"])),
            ).fetchone()
        return {"history_id": str(row[0]), "analyzed_at": row[1], **payload}

    def list_history(self, user_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("select history_id, analyzed_at, date_from, date_to, line_id, equipment_id, report_json from analysis_history where user_id = %s order by analyzed_at desc", (user_id,)).fetchall()
        return [self._history_row(row) for row in rows]

    def get_history(self, user_id: str, history_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("select history_id, analyzed_at, date_from, date_to, line_id, equipment_id, report_json from analysis_history where user_id = %s and history_id = %s", (user_id, history_id)).fetchone()
        return None if row is None else self._history_row(row)

    @staticmethod
    def _history_row(row: Any) -> dict[str, Any]:
        report = json.loads(row[6]) if isinstance(row[6], str) else row[6]
        return {"history_id": str(row[0]), "analyzed_at": row[1], "date_from": row[2], "date_to": row[3], "line_id": row[4], "equipment_id": row[5], "report_json": report}
