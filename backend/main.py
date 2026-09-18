"""FastAPI 진입점.

LLM 호출은 여기가 아니라 services/ 아래 한곳에 모으세요.
3차 프로젝트에서 그 자리에 RAG 그래프가 들어옵니다 — 호출부가 흩어져 있으면 그때 전부 뜯어야 합니다.
"""

import logging
import os
import time
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .services.llm import DowntimeReport, generate_report, get_model_name

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="MESTORY API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    ],
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
    allow_credentials=False,
)


@app.get("/health")
def health() -> dict:
    """채점자와 배포 환경이 서비스 상태를 확인하는 곳."""
    return {"status": "ok"}


class ReportRequest(BaseModel):
    line_id: str | None = Field(default=None, description="예: LINE-A")
    equipment_id: str | None = Field(default=None, description="예: EQ-001")
    date_from: str | None = Field(default=None, description="YYYY-MM-DD, 정지 시작일 기준")
    date_to: str | None = Field(default=None, description="YYYY-MM-DD, 정지 시작일 기준")
    session_id: str | None = Field(default=None, description="대화 맥락을 이어갈 세션 ID (선택)")


@app.post("/report", response_model=DowntimeReport)
async def create_report(request: ReportRequest) -> DowntimeReport:
    """정지 로그를 조건에 맞게 조회해 원인 분석 리포트를 생성한다 (PRD F-04)."""
    request_id = str(uuid.uuid4())
    started = time.perf_counter()
    logger.info(
        "request_id=%s report 요청 시작 line_id=%s equipment_id=%s date_from=%s date_to=%s",
        request_id, request.line_id, request.equipment_id, request.date_from, request.date_to,
    )

    report = await generate_report(
        line_id=request.line_id,
        equipment_id=request.equipment_id,
        date_from=request.date_from,
        date_to=request.date_to,
        session_id=request.session_id,
    )

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    # 토큰 사용량은 Langfuse 트레이스에서 확인한다 (이 로그에는 중복 기록하지 않음).
    logger.info(
        "request_id=%s report 요청 완료 model=%s elapsed_ms=%d unclassified_count=%d",
        request_id, get_model_name(), elapsed_ms, report.unclassified_count,
    )
    return report
