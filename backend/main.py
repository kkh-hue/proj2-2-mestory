"""FastAPI 진입점.

LLM 호출은 여기가 아니라 services/ 아래 한곳에 모으세요.
3차 프로젝트에서 그 자리에 RAG 그래프가 들어옵니다 — 호출부가 흩어져 있으면 그때 전부 뜯어야 합니다.
"""

import asyncio
import logging
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from datetime import date
from typing import Literal

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator, model_validator

from .db import (
    DatabaseUnavailableError,
    get_dashboard_summary,
    get_downtime_analysis,
    get_report,
    get_session_scope,
    init_db,
    list_alerts,
    list_chat_sessions,
    list_chat_turns,
    list_equipment_status,
    list_reports,
)
from .report_email import (
    ReportEmailError,
    is_allowed_recipient,
    render_report_email,
    send_email,
)
from .scope import ScopeError, resolve_scope
from .services.llm import (
    AnalysisInfrastructureError,
    DowntimeReport,
    generate_report,
    get_model_name,
    resolve_model_name,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(_: FastAPI):
    await init_db()
    yield


app = FastAPI(title="MESTORY API", lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
    allow_credentials=False,
    # 프론트가 방금 생성한 리포트의 id를 응답 헤더로 받아 "상세 리포트 보기"에 쓴다 (F-07).
    # CORS 기본값은 "단순 헤더"만 JS에 노출하므로, 커스텀 헤더는 여기 명시해야 fetch에서 읽힌다.
    expose_headers=["X-Report-Id"],
)


@app.get("/health")
def health() -> dict:
    """채점자와 배포 환경이 서비스 상태를 확인하는 곳."""
    return {"status": "ok"}


# ─────────────────────────────────────────────
# 멀티모달 이미지 제한 (docs/specs/multimodal.md)
#
# 왜 제한을 두는가
#   ① base64는 원본 파일보다 약 33% 커진다 → 5MB 사진이 요청 본문에서는 약 6.7MB
#   ② 이미지 토큰은 gpt-4o-mini에서 1장에 25,000 토큰을 넘는다 → p95 게이트(20초)를 깬다
#   ③ 제한이 없으면 큰 파일 하나로 서버 메모리를 밀어낼 수 있다
# ─────────────────────────────────────────────
MAX_IMAGES = 3
MAX_IMAGE_BYTES = 5 * 1024 * 1024        # 1장 5MB
MAX_TOTAL_IMAGE_BYTES = 10 * 1024 * 1024  # 합계 10MB
ALLOWED_IMAGE_SUBTYPES = {"png", "jpeg", "jpg", "webp"}

# "data:image/png;base64,iVBORw0KGgo..." 를 (형식, 내용) 두 조각으로 나눈다.
# re.DOTALL: base64 안에 줄바꿈이 섞여 와도 끝까지 잡게.
_DATA_URL_RE = re.compile(r"^data:image/([A-Za-z0-9.+\-]+);base64,(.+)$", re.DOTALL)


class ReportRequest(BaseModel):
    line_id: str | None = Field(default=None, description="예: LINE-A")
    equipment_id: str | None = Field(default=None, description="예: EQ-001")
    date_from: str | None = Field(default=None, description="YYYY-MM-DD, 정지 시작일 기준")
    date_to: str | None = Field(default=None, description="YYYY-MM-DD, 정지 시작일 기준")
    session_id: str | None = Field(default=None, description="대화 맥락을 이어갈 세션 ID (선택)")
    message: str | None = Field(
        default=None,
        max_length=2000,
        description="AI 원인분석 대화형 화면에서 사용자가 직접 입력한 자유 텍스트 질문 (F-07)",
    )
    images: list[str] | None = Field(
        default=None,
        description=(
            f"에러 화면·설비 사진 data URL 목록 (예: 'data:image/png;base64,...'). "
            f"최대 {MAX_IMAGES}장, 1장 {MAX_IMAGE_BYTES // (1024 * 1024)}MB, "
            f"합계 {MAX_TOTAL_IMAGE_BYTES // (1024 * 1024)}MB. png·jpeg·webp만."
        ),
    )

    @field_validator("date_from", "date_to")
    @classmethod
    def _validate_date_format(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("날짜는 YYYY-MM-DD 형식이어야 합니다.") from exc
        if parsed.isoformat() != value:
            raise ValueError("날짜는 YYYY-MM-DD 형식이어야 합니다.")
        return value

    @model_validator(mode="after")
    def _validate_date_range(self) -> "ReportRequest":
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from은 date_to보다 늦을 수 없습니다.")
        return self

    @field_validator("images")
    @classmethod
    def _check_images(cls, value: list[str] | None) -> list[str] | None:
        """이미지 형식·용량을 여기서 끝낸다.

        여기서 ValueError를 던지면 FastAPI가 HTTP 422로 바꿔 준다 —
        서버가 죽지 않고, 무엇이 잘못됐는지 사용자에게 한국어로 전달된다.
        llm.py는 검증이 끝난 값만 받으므로 담는 일에만 집중할 수 있다.
        """
        if value is None:
            return None
        if not value:  # 빈 목록은 "이미지 없음"과 같게 취급한다
            return None
        if len(value) > MAX_IMAGES:
            raise ValueError(
                f"이미지는 최대 {MAX_IMAGES}장까지 첨부할 수 있습니다 (받은 개수: {len(value)}장)."
            )

        total_bytes = 0
        for order, raw in enumerate(value, start=1):
            matched = _DATA_URL_RE.match(raw.strip())
            if matched is None:
                raise ValueError(
                    f"{order}번째 이미지가 data URL 형식이 아닙니다. "
                    "'data:image/png;base64,...' 형태로 보내주세요."
                )

            subtype = matched.group(1).lower()
            if subtype not in ALLOWED_IMAGE_SUBTYPES:
                raise ValueError(
                    f"{order}번째 이미지 형식({subtype})은 지원하지 않습니다. "
                    f"지원 형식: {', '.join(sorted(ALLOWED_IMAGE_SUBTYPES))}."
                )

            # base64 글자 4개가 원본 3바이트 → 원본 크기는 글자 수 × 3 ÷ 4.
            # 실제로 디코딩하지 않는 이유: 5MB를 디코딩하면 응답이 그만큼 느려진다.
            payload_bytes = len(matched.group(2)) * 3 // 4
            if payload_bytes > MAX_IMAGE_BYTES:
                raise ValueError(
                    f"{order}번째 이미지가 너무 큽니다 "
                    f"(약 {payload_bytes // (1024 * 1024)}MB, 한 장 최대 "
                    f"{MAX_IMAGE_BYTES // (1024 * 1024)}MB)."
                )
            total_bytes += payload_bytes

        if total_bytes > MAX_TOTAL_IMAGE_BYTES:
            raise ValueError(
                f"이미지 합계가 너무 큽니다 (약 {total_bytes // (1024 * 1024)}MB, 최대 "
                f"{MAX_TOTAL_IMAGE_BYTES // (1024 * 1024)}MB)."
            )
        return value


# 경로가 두 개인 이유: 가이드 6쪽 공통 배포 구조가 `POST /api/agent`를 요구한다.
# 기존 `/report`를 쓰는 프론트·연습 스크립트가 있으므로 지우지 않고 둘 다 받는다.
# (FastAPI의 라우트 데코레이터는 원래 함수를 그대로 돌려주므로 이렇게 겹쳐 쓸 수 있다.)
async def _load_equipment_master() -> tuple[dict[str, str], dict[str, str]]:
    """({설비ID: 라인ID}, {설비ID: 종류}) — CSV/DB 모드 공통. 못 읽으면 None (검증만 건너뛴다)."""
    try:
        from mcp_server.tools.data_loader import load_equipment

        frame = await asyncio.to_thread(load_equipment)
        ids = frame["equipment_id"].astype(str)
        return (
            dict(zip(ids, frame["line_id"].astype(str))),
            dict(zip(ids, frame["equipment_type"].astype(str))),
        )
    except Exception as exc:
        logger.warning("설비 마스터를 읽지 못해 설비 검증을 건너뜁니다: %s", exc)
        raise DatabaseUnavailableError("설비 마스터를 조회하지 못했습니다") from exc


async def _resolve_request_scope(request: "ReportRequest") -> tuple[str | None, str | None]:
    session_scope = await get_session_scope(request.session_id) if request.message and request.session_id else None
    master = await _load_equipment_master()
    try:
        return resolve_scope(
            request.message, request.line_id, request.equipment_id,
            master[0], session_scope, master[1],
        )
    except ScopeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/agent", response_model=DowntimeReport)
@app.post("/report", response_model=DowntimeReport)
async def create_report(request: ReportRequest, response: Response) -> DowntimeReport:
    """정지 로그를 조건에 맞게 조회해 원인 분석 리포트를 생성한다 (PRD F-04)."""
    request_id = str(uuid.uuid4())
    report_id = str(uuid.uuid4())
    started = time.perf_counter()
    image_count = len(request.images) if request.images else 0
    logger.info(
        "request_id=%s report 요청 시작 line_id=%s equipment_id=%s date_from=%s date_to=%s image_count=%d",
        request_id, request.line_id, request.equipment_id, request.date_from, request.date_to, image_count,
    )

    # 조회 범위(라인·설비)를 확정한다 — "전체 라인/전체 설비"로 뭉뚱그려 저장하지 않는다.
    # 질문(message)이 있으면 질문 속 설비·라인과 세션의 이전 범위도 쓴다. docs/specs/report-scope.md
    try:
        line_id, equipment_id = await _resolve_request_scope(request)
    except DatabaseUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        report = await generate_report(
            line_id=line_id,
            equipment_id=equipment_id,
            date_from=request.date_from,
            date_to=request.date_to,
            session_id=request.session_id,
            images=request.images,
            message=request.message,
            report_id=report_id,
            # Langfuse Users 탭에서 평가(eval-runner)와 실제 사용을 가르는 "요청 출처" 라벨.
            # 로그인이 없어 사람을 식별할 수 없으므로, 사람이 아니라 어디서 온 요청인지를 붙인다.
            # 요청 본문에서 받지 않는다 — 클라이언트가 임의 값을 넣지 못하게. docs/specs/langfuse-user-id.md
            user_id="web",
        )
    except DatabaseUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AnalysisInfrastructureError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    # response_model=DowntimeReport라 본문 계약은 못 건드린다 — "상세 리포트 보기"가
    # 재조회 없이 바로 쓸 수 있게 id는 헤더로 얹어 준다 (CORS expose_headers 참고).
    response.headers["X-Report-Id"] = report_id

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    # 토큰 사용량은 Langfuse 트레이스에서 확인한다 (이 로그에는 중복 기록하지 않음).
    # image_count를 남기는 이유: 게이트가 2줄(텍스트 10초 / 이미지 20초)이라
    # 로그만 보고 어느 기준으로 볼지 가릴 수 있어야 한다.
    # model은 get_model_name()이 아니라 resolve_model_name()으로 찍는다.
    # 이미지 유무에 따라 실제로 간 모델이 다르기 때문이다 — 안 고치면 텍스트 요청도
    # vision 모델명으로 찍혀 로그가 거짓이 된다 (docs/specs/model-routing.md EC-05).
    logger.info(
        "request_id=%s report 요청 완료 model=%s elapsed_ms=%d unclassified_count=%d used_image=%s",
        request_id, resolve_model_name(image_count > 0), elapsed_ms,
        report.unclassified_count, report.used_image,
    )
    return report


# ─────────────────────────────────────────────
# 대화·리포트 조회 (F-07) — 값은 backend/db.py(Postgres)에서 온다.
# ⚠️ /chat/sessions는 /chat/{session_id}보다 먼저 와야 한다 — 안 그러면
#    "sessions"가 session_id로 매칭돼 버린다.
# ─────────────────────────────────────────────
@app.get("/chat/sessions")
async def get_chat_sessions(limit: int = 30) -> list[dict]:
    """AI 원인분석 화면 왼쪽 세션 목록용 — 세션별 첫 질문·마지막 활동 시각."""
    try:
        return await list_chat_sessions(limit)
    except DatabaseUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/chat/{session_id}")
async def get_chat_history(session_id: str) -> list[dict]:
    """AI 원인분석 대화형 화면이 새로고침/재방문 때 이전 대화를 그대로 불러오는 곳."""
    try:
        return await list_chat_turns(session_id)
    except DatabaseUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/reports")
async def get_reports(limit: int = 50) -> list[dict]:
    """리포트 목록 화면용 (요약 필드만, causes 등 큰 값은 상세 조회에서)."""
    try:
        return await list_reports(limit)
    except DatabaseUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# ─────────────────────────────────────────────
# 리포트 메일 발송 (docs/specs/report-email.md)
# ─────────────────────────────────────────────
# 메일 주소 형식 검사. email-validator 패키지를 쓰지 않고 정규식으로 하는 이유:
#   의존성을 늘리지 않는 것이 이 팀 방식이고, 위 날짜 검증도 같은 방식이다.
#   완벽한 주소 검증은 애초에 불가능하다(RFC 5322는 매우 복잡하다).
#   진짜 방어선은 허용 목록이므로, 여기서는 명백히 주소가 아닌 값만 걸러 내면 된다.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ReportEmailRequest(BaseModel):
    """받는 사람 주소 하나만 받는다.

    리포트 내용을 요청에 담지 않는 이유:
      화면이 보낸 내용을 그대로 메일에 넣으면, 누구나 요청을 조작해 아무 내용이나 담은 메일을
      우리 도메인 이름으로 보낼 수 있다. 서버는 report_id만 받고 내용은 스스로 조회한다.
    """

    to: str = Field(description="받는 사람 메일 주소 (서버 허용 목록에 있어야 한다)")

    @field_validator("to")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        address = (value or "").strip()
        if not _EMAIL_RE.match(address):
            # 여기서 ValueError를 던지면 FastAPI가 HTTP 422로 바꿔 준다 (Spec AC-04).
            raise ValueError("메일 주소 형식이 아닙니다.")
        return address


@app.post("/reports/{report_id}/email")
async def send_report_email(report_id: str, request: ReportEmailRequest) -> dict:
    """저장된 리포트를 지정한 주소로 메일 발송한다 (docs/specs/report-email.md).

    검사 순서가 중요하다 — 허용 목록을 DB 조회보다 먼저 본다.
      반대로 하면 허용되지 않은 주소로 요청했을 때도 "그 리포트가 있는지 없는지"를
      404/403으로 구분해 알려주게 된다. 먼저 막으면 그 정보가 새지 않는다.
    """
    # ① 허용 목록 (Spec AC-02·AC-05). 목록이 비어 있으면 여기서 전부 막힌다.
    if not is_allowed_recipient(request.to):
        logger.warning("허용되지 않은 수신 주소로 메일 요청이 들어왔습니다 (report_id=%s)", report_id)
        raise HTTPException(status_code=403, detail="허용되지 않은 수신 주소입니다")

    # ② 리포트 조회 (Spec AC-03). 화면이 보낸 내용이 아니라 DB에서 직접 꺼낸다.
    try:
        report = await get_report(report_id)
    except DatabaseUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if report is None:
        raise HTTPException(status_code=404, detail="리포트를 찾을 수 없습니다")

    # ③ 본문 만들기 (Spec AC-06). 링크의 앞부분은 환경변수로 받는다.
    base_url = os.getenv("FRONTEND_BASE_URL", "").strip()
    html_body, text_body = render_report_email(report, base_url)
    subject = f"[MESTORY] {report.get('equipment_id') or '전체 설비'} 정지 원인 분석 리포트"

    # ④ 발송 (Spec AC-07). 실패해도 예외가 밖으로 새지 않게 502로 바꾼다.
    try:
        await send_email(to=request.to, subject=subject, html=html_body, text=text_body)
    except ReportEmailError as exc:
        logger.warning("메일 발송 실패 (report_id=%s): %s", report_id, exc)
        raise HTTPException(status_code=502, detail="메일을 보내지 못했습니다") from exc

    logger.info("리포트 메일 발송 완료 (report_id=%s)", report_id)
    return {"ok": True, "to": request.to}


@app.get("/reports/{report_id}")
async def get_report_detail(report_id: str) -> dict:
    """"상세 리포트 보기"·엑셀/PDF 다운로드가 쓰는 상세 조회."""
    try:
        report = await get_report(report_id)
    except DatabaseUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if report is None:
        raise HTTPException(status_code=404, detail="리포트를 찾을 수 없습니다")
    return report


@app.get("/dashboard")
async def get_dashboard(as_of: date | None = None) -> dict:
    """대시보드 화면용 — KPI·추이·최근 이벤트·최근 리포트를 한 번에 (backend/db.py에서 집계).

    as_of(YYYY-MM-DD)를 주면 그 날짜를 "오늘"로 보고 다시 집계한다 (상단 날짜 선택).
    """
    try:
        return await get_dashboard_summary(as_of)
    except DatabaseUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/downtime/analysis")
async def get_downtime_analysis_view(
    date_from: date | None = None,
    date_to: date | None = None,
    line_id: str | None = None,
    equipment_id: str | None = None,
    status: Literal["all", "closed", "open"] = "all",
) -> dict:
    """다운타임 분석 화면용 — 조건에 맞는 정지를 원인(에러코드)별로 집계 (docs/specs/downtime-analysis.md)."""
    try:
        return await get_downtime_analysis(date_from, date_to, line_id, equipment_id, status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DatabaseUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/alerts")
async def get_alerts(limit: int = 30, as_of: date | None = None) -> list[dict]:
    """알림센터 화면용 — downtime_log·reports에서 파생시킨 알림 (backend/db.py 참고)."""
    try:
        return await list_alerts(limit, as_of)
    except DatabaseUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/equipment")
async def get_equipment(as_of: date | None = None) -> list[dict]:
    """설비관리 화면용 — 설비별 상태·가동률·마지막 점검일 (backend/db.py에서 집계)."""
    try:
        return await list_equipment_status(as_of)
    except DatabaseUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
