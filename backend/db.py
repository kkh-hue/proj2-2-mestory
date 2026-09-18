"""대화·리포트 영속 저장 (F-07). 담당: 홍민하

왜 필요한가
  backend/services/llm.py의 _SESSION_STORE는 프로세스 메모리 dict라서
  재배포·재시작하면 대화 기록이 통째로 사라진다. 이 파일은 그 자리를
  scripts/seed_db.py와 같은 Postgres(DATABASE_URL)로 옮긴다.

규칙 (scripts/seed_db.py, mcp_server/tools/data_loader.py와 동일)
  - psycopg[binary] (이미 requirements.txt에 있음), ORM 없이 순수 SQL
  - 접속 주소: DATABASE_URL 또는 DATABASE_PUBLIC_URL
  - "create table if not exists" — 마이그레이션 도구 없이 최초 실행 때 자동 생성

DB가 잠깐 응답하지 않아도 리포트 생성(핵심 기능) 자체는 멈추면 안 되므로,
쓰기/읽기 실패는 여기서 로그만 남기고 삼킨다 — 호출부(llm.py)는 항상
"성공하면 값, 실패하면 빈 값"을 받는다고 가정하고 쓸 수 있다.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import psycopg
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

logger = logging.getLogger(__name__)

_SCHEMA_READY = False


def _get_database_url() -> str | None:
    return os.getenv("DATABASE_URL") or os.getenv("DATABASE_PUBLIC_URL")


async def _connect() -> psycopg.AsyncConnection:
    url = _get_database_url()
    if not url:
        raise RuntimeError("DATABASE_URL(또는 DATABASE_PUBLIC_URL)이 설정되지 않았습니다.")
    return await psycopg.AsyncConnection.connect(url, connect_timeout=10)


async def init_db() -> None:
    """앱 시작 시 한 번 호출한다. 테이블이 이미 있으면 아무 일도 하지 않는다."""
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    try:
        async with await _connect() as conn:
            await conn.execute(
                """
                create table if not exists reports (
                    id                 text primary key,
                    session_id         text,
                    equipment_id       text,
                    line_id            text,
                    period             text,
                    causes             jsonb not null default '[]',
                    unclassified_count integer not null default 0,
                    confidence_note    text,
                    recommended_action text,
                    visual_findings    jsonb,
                    used_image         boolean not null default false,
                    created_at         timestamptz not null default now()
                )
                """
            )
            await conn.execute(
                """
                create table if not exists chat_messages (
                    id         bigserial primary key,
                    session_id text not null,
                    role       text not null check (role in ('user', 'assistant')),
                    content    text not null,
                    report_id  text,
                    created_at timestamptz not null default now()
                )
                """
            )
            await conn.execute(
                "create index if not exists idx_chat_messages_session "
                "on chat_messages (session_id, created_at)"
            )
            await conn.execute(
                "create index if not exists idx_reports_session on reports (session_id, created_at)"
            )
        _SCHEMA_READY = True
        logger.info("DB 스키마 준비 완료 (reports, chat_messages)")
    except Exception as exc:  # DB 없이도 서비스는 뜨게 (로컬 CSV 개발 등)
        logger.warning("DB 스키마 준비 실패 — 대화·리포트 저장이 비활성화됩니다: %s", exc)


async def save_report(report_id: str, report: Any, session_id: str | None) -> None:
    """DowntimeReport 하나를 reports 테이블에 저장한다."""
    try:
        async with await _connect() as conn:
            await conn.execute(
                """
                insert into reports
                    (id, session_id, equipment_id, line_id, period, causes,
                     unclassified_count, confidence_note, recommended_action,
                     visual_findings, used_image)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (id) do nothing
                """,
                (
                    report_id,
                    session_id,
                    report.equipment_id,
                    report.line_id,
                    report.period,
                    json.dumps([c.model_dump() for c in report.causes], ensure_ascii=False),
                    report.unclassified_count,
                    report.confidence_note,
                    report.recommended_action,
                    json.dumps(report.visual_findings, ensure_ascii=False) if report.visual_findings is not None else None,
                    report.used_image,
                ),
            )
    except Exception as exc:
        logger.warning("리포트 저장 실패 (report_id=%s): %s", report_id, exc)


async def save_message(session_id: str, role: str, content: str, report_id: str | None = None) -> None:
    try:
        async with await _connect() as conn:
            await conn.execute(
                "insert into chat_messages (session_id, role, content, report_id) values (%s, %s, %s, %s)",
                (session_id, role, content, report_id),
            )
    except Exception as exc:
        logger.warning("대화 메시지 저장 실패 (session_id=%s): %s", session_id, exc)


async def load_chat_history(session_id: str, limit: int = 10) -> list[BaseMessage]:
    """session_id의 최근 대화를 LangChain 메시지 목록으로 되돌린다 (사람/AI 합쳐 최근 limit개)."""
    try:
        async with await _connect() as conn:
            cur = await conn.execute(
                "select role, content from chat_messages where session_id = %s "
                "order by created_at desc limit %s",
                (session_id, limit),
            )
            rows = await cur.fetchall()
    except Exception as exc:
        logger.warning("대화 기록 조회 실패 (session_id=%s): %s", session_id, exc)
        return []

    messages: list[BaseMessage] = [
        HumanMessage(content=content) if role == "user" else AIMessage(content=content)
        for role, content in reversed(rows)
    ]
    return messages


async def list_chat_turns(session_id: str) -> list[dict]:
    """화면에 그대로 뿌릴 수 있는 형태로 대화 턴을 돌려준다 (assistant 턴은 report도 같이 붙인다)."""
    try:
        async with await _connect() as conn:
            cur = await conn.execute(
                "select m.role, m.content, m.report_id, m.created_at, "
                "       r.id, r.equipment_id, r.line_id, r.period, r.causes, "
                "       r.unclassified_count, r.confidence_note, r.recommended_action, "
                "       r.visual_findings, r.used_image "
                "from chat_messages m "
                "left join reports r on r.id = m.report_id "
                "where m.session_id = %s order by m.created_at asc",
                (session_id,),
            )
            rows = await cur.fetchall()
    except Exception as exc:
        logger.warning("대화 턴 조회 실패 (session_id=%s): %s", session_id, exc)
        return []

    turns: list[dict] = []
    for (role, content, report_id, created_at, r_id, equipment_id, line_id, period, causes,
         unclassified_count, confidence_note, recommended_action, visual_findings, used_image) in rows:
        turn: dict = {"role": role, "content": content, "created_at": created_at.isoformat()}
        if report_id and r_id:
            turn["report"] = {
                "id": r_id,
                "equipment_id": equipment_id,
                "line_id": line_id,
                "period": period,
                "causes": causes,
                "unclassified_count": unclassified_count,
                "confidence_note": confidence_note,
                "recommended_action": recommended_action,
                "visual_findings": visual_findings,
                "used_image": used_image,
            }
        turns.append(turn)
    return turns


async def list_reports(limit: int = 50) -> list[dict]:
    try:
        async with await _connect() as conn:
            cur = await conn.execute(
                "select id, session_id, equipment_id, line_id, period, unclassified_count, "
                "       confidence_note, recommended_action, used_image, created_at "
                "from reports order by created_at desc limit %s",
                (limit,),
            )
            rows = await cur.fetchall()
    except Exception as exc:
        logger.warning("리포트 목록 조회 실패: %s", exc)
        return []

    return [
        {
            "id": row[0], "session_id": row[1], "equipment_id": row[2], "line_id": row[3],
            "period": row[4], "unclassified_count": row[5], "confidence_note": row[6],
            "recommended_action": row[7], "used_image": row[8], "created_at": row[9].isoformat(),
        }
        for row in rows
    ]


async def get_report(report_id: str) -> dict | None:
    try:
        async with await _connect() as conn:
            cur = await conn.execute(
                "select id, session_id, equipment_id, line_id, period, causes, "
                "       unclassified_count, confidence_note, recommended_action, "
                "       visual_findings, used_image, created_at "
                "from reports where id = %s",
                (report_id,),
            )
            row = await cur.fetchone()
    except Exception as exc:
        logger.warning("리포트 조회 실패 (report_id=%s): %s", report_id, exc)
        return None

    if row is None:
        return None
    return {
        "id": row[0], "session_id": row[1], "equipment_id": row[2], "line_id": row[3],
        "period": row[4], "causes": row[5], "unclassified_count": row[6],
        "confidence_note": row[7], "recommended_action": row[8],
        "visual_findings": row[9], "used_image": row[10], "created_at": row[11].isoformat(),
    }
