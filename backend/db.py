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
from datetime import timezone
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
        return []

    turns: list[dict] = []
    for (role, content, display_content, report_id, created_at, r_id, equipment_id, line_id, period, causes,
         unclassified_count, confidence_note, recommended_action, visual_findings, used_image) in rows:
        turn: dict = {"role": role, "content": display_content or content, "created_at": created_at.isoformat()}
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
                        select coalesce(m2.display_content, m2.content)
                        from chat_messages m2
                        where m2.session_id = m.session_id and m2.role = 'user'
                        order by m2.created_at asc
                        limit 1
                    ) as title
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
        return []

    return [
        {
            "session_id": session_id,
            "title": title,
            "started_at": started_at.isoformat(),
            "last_active": last_active.isoformat(),
            "turn_count": turn_count,
        }
        for session_id, started_at, last_active, turn_count, title in rows
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


# ─────────────────────────────────────────────
# 대시보드 화면 (F-07) — KPI·추이·최근 이벤트를 한 번에 집계한다.
# equipment_master·downtime_log는 scripts/seed_db.py가 만든 시뮬레이션 테이블.
# ─────────────────────────────────────────────
def _delta(today: float, yesterday: float) -> dict:
    """"전일 대비" 배지 하나를 만든다. 어제 값이 0이면 방향을 판단할 기준이 없어 0%로 둔다."""
    if yesterday == 0:
        return {"direction": "up", "percent": 0.0}
    change = (today - yesterday) / yesterday * 100
    return {"direction": "up" if change >= 0 else "down", "percent": round(abs(change), 1)}


async def get_dashboard_summary() -> dict:
    try:
        async with await _connect() as conn:
            kpi_cur = await conn.execute(
                """
                select
                    coalesce(sum(downtime_min) filter (where start_time >= current_date and downtime_min > 0), 0),
                    coalesce(sum(downtime_min) filter (
                        where start_time >= current_date - 1 and start_time < current_date and downtime_min > 0
                    ), 0),
                    coalesce(avg(downtime_min) filter (
                        where start_time >= current_date and end_time is not null and downtime_min > 0
                    ), 0),
                    coalesce(avg(downtime_min) filter (
                        where start_time >= current_date - 1 and start_time < current_date
                        and end_time is not null and downtime_min > 0
                    ), 0)
                from downtime_log
                """
            )
            today_downtime, yesterday_downtime, today_avg_recovery, yesterday_avg_recovery = await kpi_cur.fetchone()

            equipment_count_row = await (await conn.execute("select count(*) from equipment_master")).fetchone()
            equipment_count = equipment_count_row[0] if equipment_count_row else 0

            reports_cur = await conn.execute(
                """
                select
                    count(*) filter (where created_at >= current_date),
                    count(*) filter (where created_at >= current_date - 1 and created_at < current_date)
                from reports
                """
            )
            today_reports, yesterday_reports = await reports_cur.fetchone()

            trend_cur = await conn.execute(
                """
                select date_trunc('day', start_time)::date as day, line_id,
                       coalesce(sum(downtime_min) filter (where downtime_min > 0), 0) as total_min
                from downtime_log
                where start_time >= current_date - interval '6 days'
                group by day, line_id
                order by day
                """
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
                order by d.start_time desc
                limit 10
                """
            )
            event_rows = await events_cur.fetchall()

            latest_report_cur = await conn.execute(
                "select id, equipment_id, line_id, period, causes, unclassified_count, "
                "       confidence_note, recommended_action, visual_findings, used_image, created_at "
                "from reports order by created_at desc limit 1"
            )
            latest_report_row = await latest_report_cur.fetchone()
    except Exception as exc:
        logger.warning("대시보드 집계 실패: %s", exc)
        return {
            "kpi": {"today_downtime_min": 0, "avg_recovery_min": 0, "reports_today": 0, "equipment_count": 0,
                    "utilization_pct": 100.0, "downtime_delta": _delta(0, 0), "recovery_delta": _delta(0, 0),
                    "reports_delta": _delta(0, 0), "utilization_delta": _delta(0, 0)},
            "trend": {"labels": [], "lines": []},
            "recent_events": [],
            "latest_report": None,
        }

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
# 알림센터 화면 (F-07) — 알림 전용 테이블이 없어서, 실제로 있는 두 가지 사건에서
# 만들어낸다: downtime_log(정지 발생/진행)와 reports(AI 분석 완료). "공유"·"읽음"
# 같은 계정 기반 기능은 없어서 지어내지 않고, "24시간 이내 발생"을 미확인의
# 대리 지표로 쓴다.
# ─────────────────────────────────────────────
async def list_alerts(limit: int = 30) -> list[dict]:
    try:
        async with await _connect() as conn:
            downtime_cur = await conn.execute(
                """
                select d.log_id, d.equipment_id, d.line_id, d.error_code, d.start_time,
                       (d.end_time is null) as is_open,
                       (d.start_time >= now() - interval '1 day') as is_recent,
                       e.equipment_type
                from downtime_log d
                left join equipment_master e on e.equipment_id = d.equipment_id
                where d.end_time is null or d.start_time >= now() - interval '7 days'
                order by d.start_time desc
                limit %s
                """,
                (limit,),
            )
            downtime_rows = await downtime_cur.fetchall()

            report_cur = await conn.execute(
                """
                select id, equipment_id, line_id, recommended_action, created_at,
                       (created_at >= now() - interval '1 day') as is_recent
                from reports order by created_at desc limit %s
                """,
                (limit,),
            )
            report_rows = await report_cur.fetchall()
    except Exception as exc:
        logger.warning("알림 목록 조회 실패: %s", exc)
        return []

    alerts: list[dict] = []
    for log_id, equipment_id, line_id, error_code, start_time, is_open, is_recent, equipment_type in downtime_rows:
        cause_note = f"{error_code} 관련 " if error_code else ""
        alerts.append({
            "id": f"downtime-{log_id}",
            "tone": "critical" if is_open else "warning",
            "tag": "긴급" if is_open else "주의",
            "title": f"{equipment_id} {equipment_type or ''} 정지 감지".strip(),
            "description": f"{cause_note}다운타임이 {'진행 중입니다' if is_open else '있었습니다'}. 원인 분석이 필요합니다.",
            "line_id": line_id,
            "date": start_time,
            "unread": bool(is_recent),
        })
    for report_id, equipment_id, line_id, recommended_action, created_at, is_recent in report_rows:
        alerts.append({
            "id": f"report-{report_id}",
            "tone": "analysis",
            "tag": "분석 완료",
            "title": "AI 원인 분석 완료",
            "description": f"{equipment_id}의 분석이 완료되었습니다. {recommended_action or ''}".strip(),
            "line_id": line_id,
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
    return alerts[:limit]


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


async def list_equipment_status() -> list[dict]:
    """설비별 상태·가동률·마지막 점검일을 계산한다 (그대로 저장된 컬럼이 아니라 파생값).

    - 상태: downtime_log에 아직 안 끝난(end_time is null) 기록이 있으면 "정지",
      가동률이 _ATTENTION_UTILIZATION_THRESHOLD 미만이면 "주의", 아니면 "정상".
    - 가동률: 최근 7일 중 다운타임이 차지한 비율을 뺀 값 (음수 downtime_min은
      데이터 오류라서 집계에서 뺀다 — scripts/seed_db.py의 함정 데이터 설명 참고).
    """
    try:
        async with await _connect() as conn:
            cur = await conn.execute(
                """
                select
                    e.equipment_id, e.line_id, e.equipment_type,
                    (select max(m."date") from maintenance_history m
                     where m.equipment_id = e.equipment_id) as last_checked,
                    exists(
                        select 1 from downtime_log d
                        where d.equipment_id = e.equipment_id and d.end_time is null
                    ) as is_down,
                    coalesce(sum(d2.downtime_min) filter (
                        where d2.start_time >= now() - interval '7 days' and d2.downtime_min > 0
                    ), 0) as recent_downtime_min
                from equipment_master e
                left join downtime_log d2 on d2.equipment_id = e.equipment_id
                group by e.equipment_id, e.line_id, e.equipment_type
                order by e.equipment_id
                """
            )
            rows = await cur.fetchall()
    except Exception as exc:
        logger.warning("설비 상태 조회 실패: %s", exc)
        return []

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
