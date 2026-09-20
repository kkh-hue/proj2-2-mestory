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
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

import psycopg
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from .analysis import build_analysis, resolve_period

logger = logging.getLogger(__name__)

_SCHEMA_READY = False


class DatabaseUnavailableError(RuntimeError):
    """DB 연결 또는 조회 실패를 API 계층에 알리기 위한 공통 예외."""


def _get_database_url() -> str | None:
    return os.getenv("DATABASE_URL") or os.getenv("DATABASE_PUBLIC_URL")


async def _connect() -> psycopg.AsyncConnection:
    url = _get_database_url()
    if not url:
        raise DatabaseUnavailableError("DATABASE_URL(또는 DATABASE_PUBLIC_URL)이 설정되지 않았습니다.")
    try:
        return await psycopg.AsyncConnection.connect(url, connect_timeout=10)
    except Exception as exc:
        raise DatabaseUnavailableError("데이터베이스에 연결하지 못했습니다") from exc


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
                    id              bigserial primary key,
                    session_id      text not null,
                    role            text not null check (role in ('user', 'assistant')),
                    content         text not null,
                    display_content text,
                    report_id       text,
                    created_at      timestamptz not null default now()
                )
                """
            )
            # content는 LLM 대화 맥락용(load_chat_history)이라 원래도 손대면 안 된다 —
            # 이미 배포된 테이블에 화면 표시용 칸만 뒤늦게 추가한다.
            await conn.execute(
                "alter table chat_messages add column if not exists display_content text"
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


async def get_session_scope(session_id: str) -> tuple[str | None, str | None] | None:
    """그 세션에서 마지막으로 확정된 (line_id, equipment_id). 후속 질문이 같은 설비를 이어 가게 한다.

    "전체 라인"/"전체 설비"로 저장된 옛 리포트는 범위가 아니므로 건너뛴다.
    """
    try:
        async with await _connect() as conn:
            cur = await conn.execute(
                "select line_id, equipment_id from reports "
                "where session_id = %s and (equipment_id like 'EQ-%%' or line_id like 'LINE-%%') "
                "order by created_at desc limit 1",
                (session_id,),
            )
            row = await cur.fetchone()
    except Exception as exc:
        logger.warning("세션 범위 조회 실패 (session_id=%s): %s", session_id, exc)
        raise DatabaseUnavailableError("데이터베이스에서 세션 범위를 조회하지 못했습니다") from exc
    if row is None:
        return None
    line_id = row[0] if row[0] and row[0].startswith("LINE-") else None
    equipment_id = row[1] if row[1] and row[1].startswith("EQ-") else None
    return line_id, equipment_id


async def save_message(
    session_id: str,
    role: str,
    content: str,
    report_id: str | None = None,
    display_content: str | None = None,
) -> None:
    """content는 LLM 대화 맥락용(원문 그대로), display_content는 화면 표시용(짧고 사람이 읽는 문장).

    display_content를 안 주면(기존 호출부) content를 그대로 화면에도 쓴다 — 회귀 없음.
    """
    try:
        async with await _connect() as conn:
            await conn.execute(
                "insert into chat_messages (session_id, role, content, display_content, report_id) "
                "values (%s, %s, %s, %s, %s)",
                (session_id, role, content, display_content, report_id),
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
        raise DatabaseUnavailableError("데이터베이스에서 대화 기록을 조회하지 못했습니다") from exc

    messages: list[BaseMessage] = [
        HumanMessage(content=content) if role == "user" else AIMessage(content=content)
        for role, content in reversed(rows)
    ]
    return messages


def legacy_display_text(role: str, content: str) -> str:
    """display_content 칸이 생기기 전에 저장된 행(값이 NULL)을 화면용 문장으로 복원한다.

    DB를 고쳐 쓰지 않고 읽을 때만 원문에서 뽑아낸다 — content는 LLM 맥락용이라 건드리면 안 된다.
    """
    if role == "user":
        question = re.search(r"사용자 질문: (.+?)\n위 질문에 특히", content, re.S)
        if question:
            return question.group(1).strip()
        cond = re.search(r"- 기간: (.+)\n- 라인: (.+)\n- 설비: (.+)", content)
        if cond:
            return f"{cond.group(1).strip()} · {cond.group(2).strip()} · {cond.group(3).strip()} 원인 분석 요청"
        return content
    try:
        action = json.loads(content).get("recommended_action")
    except (ValueError, AttributeError):
        return content
    return action or "원인 분석 리포트가 생성되었습니다."


async def list_chat_turns(session_id: str) -> list[dict]:
    """화면에 그대로 뿌릴 수 있는 형태로 대화 턴을 돌려준다 (assistant 턴은 report도 같이 붙인다)."""
    try:
        async with await _connect() as conn:
            cur = await conn.execute(
                "select m.role, m.content, m.display_content, m.report_id, m.created_at, "
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
        raise DatabaseUnavailableError("데이터베이스에서 대화 기록을 조회하지 못했습니다") from exc

    turns: list[dict] = []
    for (role, content, display_content, report_id, created_at, r_id, equipment_id, line_id, period, causes,
         unclassified_count, confidence_note, recommended_action, visual_findings, used_image) in rows:
        turn: dict = {"role": role, "content": display_content or legacy_display_text(role, content), "created_at": created_at.isoformat()}
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


async def list_chat_sessions(limit: int = 30) -> list[dict]:
    """AI 원인분석 화면 왼쪽에 띄울 대화 세션 목록. 세션 전용 테이블이 없어서
    chat_messages를 session_id로 묶어 만든다 — 제목은 그 세션의 첫 user 메시지."""
    try:
        async with await _connect() as conn:
            cur = await conn.execute(
                """
                select
                    m.session_id,
                    min(m.created_at) as started_at,
                    max(m.created_at) as last_active,
                    count(*) filter (where m.role = 'user') as turn_count,
                    (
                        select m2.display_content
                        from chat_messages m2
                        where m2.session_id = m.session_id and m2.role = 'user'
                        order by m2.created_at asc
                        limit 1
                    ) as title,
                    (
                        select m2.content
                        from chat_messages m2
                        where m2.session_id = m.session_id and m2.role = 'user'
                        order by m2.created_at asc
                        limit 1
                    ) as first_content
                from chat_messages m
                group by m.session_id
                order by max(m.created_at) desc
                limit %s
                """,
                (limit,),
            )
            rows = await cur.fetchall()
    except Exception as exc:
        logger.warning("대화 세션 목록 조회 실패: %s", exc)
        raise DatabaseUnavailableError("데이터베이스에서 대화 세션을 조회하지 못했습니다") from exc

    return [
        {
            "session_id": session_id,
            "title": title or (legacy_display_text("user", first_content) if first_content else None),
            "started_at": started_at.isoformat(),
            "last_active": last_active.isoformat(),
            "turn_count": turn_count,
        }
        for session_id, started_at, last_active, turn_count, title, first_content in rows
    ]


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
        raise DatabaseUnavailableError("데이터베이스에서 리포트 목록을 조회하지 못했습니다") from exc

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
        raise DatabaseUnavailableError("데이터베이스에서 리포트를 조회하지 못했습니다") from exc

    if row is None:
        return None
    return {
        "id": row[0], "session_id": row[1], "equipment_id": row[2], "line_id": row[3],
        "period": row[4], "causes": row[5], "unclassified_count": row[6],
        "confidence_note": row[7], "recommended_action": row[8],
        "visual_findings": row[9], "used_image": row[10], "created_at": row[11].isoformat(),
    }


# ─────────────────────────────────────────────
# 대시보드 화면 (F-07) — KPI·추이·최근 이벤트를 한 번에 집계한다.
# equipment_master·downtime_log는 scripts/seed_db.py가 만든 시뮬레이션 테이블.
# ─────────────────────────────────────────────
# as_of를 안 준 기본 기준일. 서버(Railway)는 UTC라 UTC 날짜를 쓰면 한국 시간 오전 9시 전까지
# 하루 전 날짜로 계산된다 — 프론트가 보내는 브라우저 로컬(한국) 날짜와 어긋나므로 KST로 맞춘다.
_KST = timezone(timedelta(hours=9))


def _today_kst() -> date:
    return datetime.now(_KST).date()


def _kst_midnight(day: date) -> datetime:
    """reports.created_at은 timestamptz라 date를 그대로 비교하면 DB 세션 시간대(UTC) 자정으로 잘려
    KST 00~09시에 만든 리포트가 "어제"로 집계된다. downtime_log의 timestamp(시간대 없음)는
    시뮬레이션 데이터가 이미 한국 시각이라 date로 비교해도 맞다 — 리포트 쪽만 KST 경계를 명시한다."""
    return datetime(day.year, day.month, day.day, tzinfo=_KST)


def _cutoff(as_of: date | None) -> datetime:
    """"이 시각 이전에 시작한 일만 일어난 일"로 보는 기준 시각 (시간대 없는 KST 값).

    오늘(as_of를 안 줬거나 오늘 날짜)이면 진짜 지금 — 아직 오지 않은 시각의 이벤트는 넣지 않고,
    자정을 넘겨 곧 끝날 다운타임 때문에 "하루 끝" 기준으로 정지가 되는 일도 없앤다.
    지난 날짜(또는 미래 날짜)는 그 날이 끝나는 시점(다음 날 00:00)의 상태를 본다.
    downtime_log.start_time은 시간대 없는 KST 값이라 이 값과 그대로 비교한다.
    """
    now = datetime.now(_KST)
    day = as_of or now.date()
    if day == now.date():
        return now.replace(tzinfo=None)
    return datetime(day.year, day.month, day.day) + timedelta(days=1)


def _aware(moment: datetime) -> datetime:
    """_cutoff 값을 reports.created_at(timestamptz)과 비교할 수 있게 KST 시간대를 붙인다."""
    return moment.replace(tzinfo=_KST)


def _delta(today: float, yesterday: float) -> dict:
    """"전일 대비" 배지 하나를 만든다. 어제 값이 0이면 방향을 판단할 기준이 없어 0%로 둔다."""
    if yesterday == 0:
        return {"direction": "up", "percent": 0.0}
    change = (today - yesterday) / yesterday * 100
    return {"direction": "up" if change >= 0 else "down", "percent": round(abs(change), 1)}


async def get_dashboard_summary(as_of: date | None = None) -> dict:
    """as_of를 안 주면 오늘 기준(기존과 동일). 주면 "그 날짜를 오늘로 보고" 어제 대비·
    최근 7일 추이를 그 날짜 기준으로 다시 계산한다 (대시보드 상단 날짜 선택용)."""
    day_start = as_of or _today_kst()
    cutoff = _cutoff(as_of)  # 배타적 상한 — 없으면 미래 날짜 데이터가 새 나간다
    yesterday_start = day_start - timedelta(days=1)
    # "전일 대비"는 같은 경과 시간끼리 비교한다. 오늘 오후 4시까지를 어제 하루 전체와 견주면
    # 낮에는 항상 다운타임이 줄어든 것처럼 나온다. 지난 날짜는 경과가 하루라 어제 전체와 같다.
    yesterday_cutoff = datetime(yesterday_start.year, yesterday_start.month, yesterday_start.day) + (
        cutoff - datetime(day_start.year, day_start.month, day_start.day)
    )
    trend_start = day_start - timedelta(days=6)

    try:
        async with await _connect() as conn:
            kpi_cur = await conn.execute(
                """
                select
                    coalesce(sum(downtime_min) filter (
                        where start_time >= %s and start_time < %s and downtime_min > 0
                    ), 0),
                    coalesce(sum(downtime_min) filter (
                        where start_time >= %s and start_time < %s and downtime_min > 0
                    ), 0),
                    coalesce(avg(downtime_min) filter (
                        where start_time >= %s and start_time < %s and end_time is not null and downtime_min > 0
                    ), 0),
                    coalesce(avg(downtime_min) filter (
                        where start_time >= %s and start_time < %s
                        and end_time is not null and downtime_min > 0
                    ), 0)
                from downtime_log
                """,
                (
                    day_start, cutoff,
                    yesterday_start, yesterday_cutoff,
                    day_start, cutoff,
                    yesterday_start, yesterday_cutoff,
                ),
            )
            today_downtime, yesterday_downtime, today_avg_recovery, yesterday_avg_recovery = await kpi_cur.fetchone()

            equipment_count_row = await (await conn.execute("select count(*) from equipment_master")).fetchone()
            equipment_count = equipment_count_row[0] if equipment_count_row else 0

            reports_cur = await conn.execute(
                """
                select
                    count(*) filter (where created_at >= %s and created_at < %s),
                    count(*) filter (where created_at >= %s and created_at < %s)
                from reports
                """,
                (
                    _kst_midnight(day_start), _aware(cutoff),
                    _kst_midnight(yesterday_start), _aware(yesterday_cutoff),
                ),
            )
            today_reports, yesterday_reports = await reports_cur.fetchone()

            trend_cur = await conn.execute(
                """
                select date_trunc('day', start_time)::date as day, line_id,
                       coalesce(sum(downtime_min) filter (where downtime_min > 0), 0) as total_min
                from downtime_log
                where start_time >= %s and start_time < %s
                group by day, line_id
                order by day
                """,
                (trend_start, cutoff),
            )
            trend_rows = await trend_cur.fetchall()

            events_cur = await conn.execute(
                """
                select d.log_id, d.equipment_id, e.equipment_type, d.line_id, d.start_time, d.end_time,
                       d.downtime_min, r.causes, r.recommended_action
                from downtime_log d
                left join equipment_master e on e.equipment_id = d.equipment_id
                left join lateral (
                    select causes, recommended_action from reports rr
                    where rr.equipment_id = d.equipment_id
                    order by rr.created_at desc limit 1
                ) r on true
                where d.start_time < %s
                order by d.start_time desc
                limit 10
                """,
                (cutoff,),
            )
            event_rows = await events_cur.fetchall()

            latest_report_cur = await conn.execute(
                "select id, equipment_id, line_id, period, causes, unclassified_count, "
                "       confidence_note, recommended_action, visual_findings, used_image, created_at "
                "from reports where created_at < %s order by created_at desc limit 1",
                (_aware(cutoff),),
            )
            latest_report_row = await latest_report_cur.fetchone()
    except Exception as exc:
        logger.warning("대시보드 집계 실패: %s", exc)
        raise DatabaseUnavailableError("데이터베이스에서 대시보드 데이터를 조회하지 못했습니다") from exc

    # 라인별 일별 다운타임을 "라벨(날짜) × 라인" 표로 펼친다 — 값 없는 칸은 0.
    days = sorted({row[0] for row in trend_rows})
    line_ids = sorted({row[1] for row in trend_rows})
    by_day_line = {(row[0], row[1]): float(row[2]) for row in trend_rows}
    trend = {
        "labels": [d.isoformat() for d in days],
        "lines": [
            {"key": line_id, "values": [round(by_day_line.get((d, line_id), 0.0) / 60, 2) for d in days]}
            for line_id in line_ids
        ],
    }

    recent_events = []
    for log_id, equipment_id, equipment_type, line_id, start_time, end_time, downtime_min, causes, recommended_action in event_rows:
        top_cause = causes[0] if causes else None
        recent_events.append({
            "log_id": log_id,
            "equipment_id": equipment_id,
            "equipment_type": equipment_type,
            "line_id": line_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat() if end_time else None,
            "downtime_min": float(downtime_min) if downtime_min is not None else None,
            "status": "복구 완료" if end_time is not None else "진행 중",
            # 다운타임과 리포트를 정확한 기간으로 맞춰 잇지 않고, 같은 설비의 가장 최근
            # 리포트를 참고용으로만 붙인다 — 정확히 이 사건의 원인이라는 보장은 없다.
            "severity": top_cause["severity"] if top_cause else "판정 불가",
            "cause": top_cause["description"] if top_cause else (recommended_action or "아직 분석되지 않음"),
        })

    latest_report = None
    if latest_report_row:
        latest_report = {
            "id": latest_report_row[0], "equipment_id": latest_report_row[1], "line_id": latest_report_row[2],
            "period": latest_report_row[3], "causes": latest_report_row[4],
            "unclassified_count": latest_report_row[5], "confidence_note": latest_report_row[6],
            "recommended_action": latest_report_row[7], "visual_findings": latest_report_row[8],
            "used_image": latest_report_row[9], "created_at": latest_report_row[10].isoformat(),
        }

    # 가동률 = 100% - (오늘 다운타임이 "설비 수 × 24시간" 중 차지한 비율).
    # equipment_count가 0이면(마스터 데이터 없음) 나눗셈을 할 수 없어 100%로 둔다.
    def _utilization(downtime_min: float) -> float:
        if equipment_count == 0:
            return 100.0
        return max(0.0, min(100.0, 100.0 - (downtime_min / (equipment_count * 24 * 60) * 100)))

    today_utilization = _utilization(float(today_downtime))
    yesterday_utilization = _utilization(float(yesterday_downtime))

    return {
        "kpi": {
            "today_downtime_min": float(today_downtime),
            "avg_recovery_min": round(float(today_avg_recovery), 1),
            "reports_today": today_reports,
            "equipment_count": equipment_count,
            "utilization_pct": round(today_utilization, 1),
            "downtime_delta": _delta(float(today_downtime), float(yesterday_downtime)),
            "recovery_delta": _delta(float(today_avg_recovery), float(yesterday_avg_recovery)),
            "reports_delta": _delta(float(today_reports), float(yesterday_reports)),
            "utilization_delta": _delta(today_utilization, yesterday_utilization),
        },
        "trend": trend,
        "recent_events": recent_events,
        "latest_report": latest_report,
    }


# ─────────────────────────────────────────────
# 다운타임 분석 화면 — 조건(기간·라인·설비·상태)에 맞는 정지를 에러코드(원인)별로 집계한다.
# 집계 후처리(상위 N + 기타, 비중)는 backend/analysis.py. 설계: docs/specs/downtime-analysis.md
# 조회 실패는 다른 화면처럼 빈 값으로 감추지 않고 예외를 올린다 — 0건과 구분돼야 해서.
# ─────────────────────────────────────────────
# 종료됐는데 시간이 0 이하/NULL인 행 = 데이터 오류 (scripts/seed_db.py의 함정 데이터)
_INVALID_DOWNTIME = "(d.end_time is not null and (d.downtime_min is null or d.downtime_min <= 0))"


async def get_downtime_analysis(
    date_from: date | None = None,
    date_to: date | None = None,
    line_id: str | None = None,
    equipment_id: str | None = None,
    status: str = "all",
) -> dict:
    start, end = resolve_period(date_from, date_to, _today_kst())

    conds = ["d.start_time >= %s", "d.start_time < %s"]
    params: list[Any] = [start, end + timedelta(days=1)]
    if line_id:
        conds.append("d.line_id = %s")
        params.append(line_id)
    if equipment_id:
        conds.append("d.equipment_id = %s")
        params.append(equipment_id)
    if status == "closed":
        conds.append("d.end_time is not null")
    elif status == "open":
        conds.append("d.end_time is null")
    where = " and ".join(conds)

    async with await _connect() as conn:
        cause_cur = await conn.execute(
            f"""
            select coalesce(d.error_code, '미상'), ec.description, ec.category,
                   count(*) filter (where not {_INVALID_DOWNTIME}),
                   coalesce(sum(d.downtime_min) filter (where d.downtime_min > 0), 0),
                   max(d.start_time) filter (where not {_INVALID_DOWNTIME}),
                   ec.typical_cause, ec.typical_duration_min_range, ec.severity_hint
            from downtime_log d
            left join error_code_dict ec on ec.error_code = d.error_code
            where {where}
            group by coalesce(d.error_code, '미상'), ec.description, ec.category,
                     ec.typical_cause, ec.typical_duration_min_range, ec.severity_hint
            having count(*) filter (where not {_INVALID_DOWNTIME}) > 0
            """,
            params,
        )
        cause_rows = await cause_cur.fetchall()

        top_cur = await conn.execute(
            f"""
            select d.equipment_id, e.equipment_type,
                   coalesce(sum(d.downtime_min) filter (where d.downtime_min > 0), 0) as total
            from downtime_log d
            left join equipment_master e on e.equipment_id = d.equipment_id
            where {where}
            group by d.equipment_id, e.equipment_type
            order by total desc, d.equipment_id
            limit 1
            """,
            params,
        )
        top_row = await top_cur.fetchone()

        review_cur = await conn.execute(
            f"""
            select count(*) filter (where {_INVALID_DOWNTIME})
                 + count(*) filter (where not {_INVALID_DOWNTIME} and ec.error_code is null)
            from downtime_log d
            left join error_code_dict ec on ec.error_code = d.error_code
            where {where}
            """,
            params,
        )
        (needs_review,) = await review_cur.fetchone()

    top_equipment_row = top_row if top_row and top_row[2] and float(top_row[2]) > 0 else None
    return build_analysis(cause_rows, top_equipment_row, needs_review or 0, start, end)


# ─────────────────────────────────────────────
# 알림센터 화면 (F-07) — 알림 전용 테이블이 없어서, 실제로 있는 두 가지 사건에서
# 만들어낸다: downtime_log(정지 발생/진행)와 reports(AI 분석 완료). "공유"·"읽음"
# 같은 계정 기반 기능은 없어서 지어내지 않고, "24시간 이내 발생"을 미확인의
# 대리 지표로 쓴다.
# ─────────────────────────────────────────────
def _line_name(line_id: str | None) -> str:
    """LINE-A → A라인. 라인 코드가 아니면 그대로 (사전에 없는 값을 지어내지 않는다)."""
    match = re.match(r"^LINE-(.+)$", line_id or "", re.IGNORECASE)
    return f"{match.group(1)}라인" if match else (line_id or "")


def _scope_name(line_id: str | None, equipment_id: str | None, equipment_type: str | None) -> str:
    """알림에 쓰는 사람이 읽는 범위 표기: "E라인 · 컨베이어 · EQ-057" / "B라인 전체 설비"."""
    if equipment_id and equipment_id.startswith("EQ-"):
        parts = [_line_name(line_id), equipment_type, equipment_id]
        return " · ".join(p for p in parts if p)
    if line_id and line_id.startswith("LINE-"):
        return f"{_line_name(line_id)} 전체 설비"
    return "전체 설비"


def _period_covers(period: str | None, day: date) -> bool:
    """리포트 period("2026-09-14 ~ 2026-09-20", "전체 ~ 전체")가 그 날을 포함하는지."""
    if not period or "~" not in period:
        return True
    start_text, end_text = (p.strip() for p in period.split("~", 1))
    try:
        if start_text != "전체" and day < date.fromisoformat(start_text):
            return False
        if end_text != "전체" and day > date.fromisoformat(end_text):
            return False
    except ValueError:
        return True
    return True


def _already_analyzed(line_id: str | None, equipment_id: str | None, day: date,
                      scopes: list[tuple[str | None, str | None, str | None]]) -> bool:
    """이 정지 기록을 이미 다룬 리포트(같은 설비, 또는 그 라인 전체를 본 리포트)가 있는가."""
    for r_line, r_equipment, r_period in scopes:
        if not _period_covers(r_period, day):
            continue
        if r_equipment and r_equipment.startswith("EQ-"):
            if r_equipment == equipment_id:
                return True
        elif r_line and r_line.startswith("LINE-") and r_line == line_id:
            return True
    return False


async def list_alerts(limit: int = 30, as_of: date | None = None) -> list[dict]:
    """as_of를 안 주면 오늘 기준(기존과 동일). 주면 그 날짜를 "지금"으로 보고 다시 계산한다.

    ⚠️ end_time is null(진행 중) 다운타임은 원래 시간 제한이 없었는데, 이 시뮬레이션
    데이터엔 미래 날짜 행도 섞여 있어(예: 2026-11) 그런 행이 항상 "가장 최근"으로
    정렬 상단을 다 차지해 분석완료(report) 알림이 목록에서 밀려나는 문제가 있었다.
    start_time < day_end로 상한을 걸어 고쳤다.
    """
    day_start = as_of or _today_kst()
    day_end = day_start + timedelta(days=1)
    cutoff = _cutoff(as_of)
    window_start = day_end - timedelta(days=7)
    recent_start = day_end - timedelta(days=1)

    # 알림도 설비현황과 같은 "현재 상태"를 기준으로 보여 준다. 상태 계산을 여기서
    # 다시 구현하면 7일 가동률·정지 판정의 기준이 다시 어긋날 수 있으므로, 설비현황의
    # 파생 결과를 그대로 사용한다.
    equipment_status_by_id = {
        item["equipment_id"]: item["status"]
        for item in await list_equipment_status(as_of)
    }

    try:
        async with await _connect() as conn:
            downtime_cur = await conn.execute(
                """
                select d.log_id, d.equipment_id, d.line_id, d.error_code, d.start_time,
                       (d.end_time is null) as is_open,
                       (d.start_time >= %s) as is_recent,
                       e.equipment_type, e.line_id as master_line_id,
                       ec.description as error_description
                from downtime_log d
                left join equipment_master e on e.equipment_id = d.equipment_id
                left join error_code_dict ec on ec.error_code = d.error_code
                where d.start_time < %s and (d.end_time is null or d.start_time >= %s)
                order by d.start_time desc
                """,
                (recent_start, cutoff, window_start),
            )
            downtime_rows = await downtime_cur.fetchall()

            report_cur = await conn.execute(
                """
                select r.id, r.equipment_id, r.line_id, r.recommended_action, r.created_at,
                       (r.created_at >= %s) as is_recent, e.equipment_type, e.line_id
                from reports r left join equipment_master e on e.equipment_id = r.equipment_id
                where r.created_at < %s order by r.created_at desc limit %s
                """,
                (_kst_midnight(recent_start), _aware(cutoff), limit),
            )
            report_rows = await report_cur.fetchall()

            # 이미 리포트로 분석된 정지의 원본 "정지 감지" 알림을 가리기 위한 범위 목록
            scope_cur = await conn.execute(
                "select line_id, equipment_id, period from reports where created_at < %s",
                (_aware(cutoff),),
            )
            analyzed_scopes = await scope_cur.fetchall()
    except Exception as exc:
        logger.warning("알림 목록 조회 실패: %s", exc)
        raise DatabaseUnavailableError("데이터베이스에서 알림을 조회하지 못했습니다") from exc

    downtime_alerts: list[dict] = []
    for (log_id, equipment_id, line_id, error_code, start_time, is_open, is_recent,
         equipment_type, master_line_id, error_description) in downtime_rows:
        # 분석이 끝난 설비의 원본 정지 알림은 숨긴다 — "분석 완료" 알림이 그 자리를 대신한다.
        # (진행 중인 정지는 분석 후에도 아직 끝나지 않았으므로 계속 보여 준다.)
        if not is_open and _already_analyzed(line_id, equipment_id, start_time.date(), analyzed_scopes):
            continue
        equipment_status = equipment_status_by_id.get(equipment_id)
        # 복구돼 정상인 설비의 과거 이벤트는 현재 알림 목록에서 제외한다. 마스터에
        # 없는 설비는 설비현황과 비교할 수 없으므로 기존 이벤트 표기를 유지한다.
        if equipment_status == "정상":
            continue
        # 마스터에 없는 설비(예: EQ-058)는 설비현황에 나오지 않아 눌러도 대응 화면이 없다.
        # 설비현황 조회가 통째로 실패해 목록이 비었을 때는 전부 숨기지 않도록 그대로 둔다.
        if equipment_status is None and equipment_status_by_id:
            continue
        if equipment_status is None:
            tone = "critical" if is_open else "warning"
            tag = "긴급" if is_open else "주의"
        else:
            tone = "critical" if equipment_status == "정지" else "warning"
            tag = "긴급" if equipment_status == "정지" else "주의"
        display_line_id = master_line_id or line_id
        # 문구는 설비 상태가 아니라 이 행 자신의 종료 여부로 정한다. 설비가 "정지"여도
        # (예: 자정에 걸친 다른 다운타임 때문에) 이미 끝난 과거 행까지 "진행 중"이라고 하면 사실과 다르다.
        is_currently_stopped = is_open
        # 코드(E-102)가 아니라 사람이 읽는 이름(예: 서보모터 과전류 트립)을 보여준다.
        # 사전에 없는 코드는 지어내지 않고 코드 그대로 둔다.
        cause_note = f"{error_description or error_code} 관련 " if error_code else ""
        downtime_alerts.append({
            "id": f"downtime-{log_id}",
            "tone": tone,
            "tag": tag,
            "title": f"{_scope_name(display_line_id, equipment_id, equipment_type)} 정지 감지",
            "description": f"{cause_note}다운타임이 {'진행 중입니다' if is_currently_stopped else '있었습니다'}. 원인 분석이 필요합니다.",
            "line_id": display_line_id,
            "equipment_id": equipment_id,
            "date": start_time,
            "unread": bool(is_recent),
        })
    # 정상 설비를 뺀 뒤에 제한해야 최신 정상 이벤트가 많아도 주의·정지 설비의
    # 알림이 밀려나지 않는다. reports는 기존처럼 별도 limit 목록을 유지한다.
    alerts: list[dict] = downtime_alerts[:limit]
    for report_id, equipment_id, line_id, recommended_action, created_at, is_recent, equipment_type, master_line in report_rows:
        # 화면으로 넘어갈 때 쓰는 값은 코드(LINE-E, EQ-057), 보이는 문장은 이름으로 만든다.
        scope_equipment = equipment_id if equipment_id and equipment_id.startswith("EQ-") else None
        scope_line = master_line or (line_id if line_id and line_id.startswith("LINE-") else None)
        scope_name = _scope_name(scope_line, scope_equipment, equipment_type)
        alerts.append({
            "id": f"report-{report_id}",
            "tone": "analysis",
            "tag": "분석 완료",
            "title": "AI 원인 분석 완료",
            "description": f"{scope_name} 분석이 완료되었습니다. {recommended_action or ''}".strip(),
            "line_id": scope_line,
            "equipment_id": scope_equipment,
            "date": created_at,
            "unread": bool(is_recent),
        })

    # downtime_log.start_time은 timestamp(시간대 없음), reports.created_at은
    # timestamptz(시간대 있음)라 그냥 정렬하면 "naive/aware 못 섞는다"는 TypeError가 난다.
    # DB 세션 시간대가 UTC라고 보고 naive 쪽에 UTC를 붙여 맞춘다.
    def _sort_key(alert: dict):
        date = alert["date"]
        return date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date

    alerts.sort(key=_sort_key, reverse=True)
    for alert in alerts:
        alert["date"] = alert["date"].isoformat()
    # 여기서 다시 [:limit]로 자르지 않는다 — downtime·report 두 종류가 이미 각자
    # limit만큼 따로 뽑혀 있는데, 여기서 합친 걸 한 번 더 자르면 한쪽이 많을 때
    # 다른 쪽(특히 report=분석완료, 건수가 원래 적다)이 통째로 밀려날 수 있다.
    return alerts


# ─────────────────────────────────────────────
# 설비관리 화면 (F-07) — reports/chat_messages와는 다른 테이블을 읽는다.
# equipment_master·downtime_log·maintenance_history는 scripts/seed_db.py가 만든
# 시뮬레이션 데이터 테이블이라, MESTORY_DATA_SOURCE=db로 시딩된 환경에서만 값이 채워진다.
# ─────────────────────────────────────────────
_RECENT_WINDOW_MINUTES = 7 * 24 * 60  # "최근 7일" 가동률 계산용


_ATTENTION_UTILIZATION_THRESHOLD = 95.0
# ⚠️ recent_downtime_count > 0 (다운타임 1건이라도 있으면 "주의")로 판정하던
# 이전 버전은 실데이터에서 57대 전부가 "주의"로 뜨는 버그였다(거의 모든 설비가
# 최근 7일 안에 짧은 다운타임을 한 번씩은 겪음). 가동률 분포(약 90~98%, 대부분
# 95% 이상에 몰려 있고 95.0% 아래는 소수 이상치)를 보고 이 값으로 다시 잡았다.


async def list_equipment_status(as_of: date | None = None) -> list[dict]:
    """설비별 상태·가동률·마지막 점검일을 계산한다 (그대로 저장된 컬럼이 아니라 파생값).

    - 상태: as_of 시점에 아직 안 끝난(end_time is null 또는 그 시점 이후 종료) 다운타임이
      있으면 "정지", 가동률이 _ATTENTION_UTILIZATION_THRESHOLD 미만이면 "주의", 아니면 "정상".
    - 가동률: as_of 기준 최근 7일 중 다운타임이 차지한 비율을 뺀 값 (음수 downtime_min은
      데이터 오류라서 집계에서 뺀다 — scripts/seed_db.py의 함정 데이터 설명 참고).
    - as_of를 안 주면 오늘 기준(기존과 동일).
    """
    day_start = as_of or _today_kst()
    day_end = day_start + timedelta(days=1)
    cutoff = _cutoff(as_of)
    window_start = day_end - timedelta(days=7)

    try:
        async with await _connect() as conn:
            cur = await conn.execute(
                """
                select
                    e.equipment_id, e.line_id, e.equipment_type,
                    (select max(m."date") from maintenance_history m
                     where m.equipment_id = e.equipment_id and m."date" < %s) as last_checked,
                    exists(
                        select 1 from downtime_log d
                        where d.equipment_id = e.equipment_id and d.start_time < %s
                          and (d.end_time is null or d.end_time >= %s)
                    ) as is_down,
                    coalesce(sum(d2.downtime_min) filter (
                        where d2.start_time >= %s and d2.start_time < %s and d2.downtime_min > 0
                    ), 0) as recent_downtime_min
                from equipment_master e
                left join downtime_log d2 on d2.equipment_id = e.equipment_id
                group by e.equipment_id, e.line_id, e.equipment_type
                order by e.equipment_id
                """,
                (cutoff, cutoff, cutoff, window_start, cutoff),
            )
            rows = await cur.fetchall()
    except Exception as exc:
        logger.warning("설비 상태 조회 실패: %s", exc)
        raise DatabaseUnavailableError("데이터베이스에서 설비 상태를 조회하지 못했습니다") from exc

    result: list[dict] = []
    for equipment_id, line_id, equipment_type, last_checked, is_down, recent_downtime_min in rows:
        utilization_pct = max(0.0, min(100.0, 100.0 - (float(recent_downtime_min or 0) / _RECENT_WINDOW_MINUTES * 100)))
        if is_down:
            status = "정지"
        elif utilization_pct < _ATTENTION_UTILIZATION_THRESHOLD:
            status = "주의"
        else:
            status = "정상"
        result.append({
            "equipment_id": equipment_id,
            "line_id": line_id,
            "equipment_type": equipment_type,
            "status": status,
            "utilization_pct": round(utilization_pct, 1),
            "last_checked": last_checked.isoformat() if last_checked else None,
        })
    return result
