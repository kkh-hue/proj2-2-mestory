"""FastAPI 진입점.

LLM 호출은 여기가 아니라 services/ 아래 한곳에 모으세요.
3차 프로젝트에서 그 자리에 RAG 그래프가 들어옵니다 — 호출부가 흩어져 있으면 그때 전부 뜯어야 합니다.
"""

import logging
import os
import re
import time
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

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
    images: list[str] | None = Field(
        default=None,
        description=(
            f"에러 화면·설비 사진 data URL 목록 (예: 'data:image/png;base64,...'). "
            f"최대 {MAX_IMAGES}장, 1장 {MAX_IMAGE_BYTES // (1024 * 1024)}MB, "
            f"합계 {MAX_TOTAL_IMAGE_BYTES // (1024 * 1024)}MB. png·jpeg·webp만."
        ),
    )

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
@app.post("/api/agent", response_model=DowntimeReport)
@app.post("/report", response_model=DowntimeReport)
async def create_report(request: ReportRequest) -> DowntimeReport:
    """정지 로그를 조건에 맞게 조회해 원인 분석 리포트를 생성한다 (PRD F-04)."""
    request_id = str(uuid.uuid4())
    started = time.perf_counter()
    image_count = len(request.images) if request.images else 0
    logger.info(
        "request_id=%s report 요청 시작 line_id=%s equipment_id=%s date_from=%s date_to=%s image_count=%d",
        request_id, request.line_id, request.equipment_id, request.date_from, request.date_to, image_count,
    )

    report = await generate_report(
        line_id=request.line_id,
        equipment_id=request.equipment_id,
        date_from=request.date_from,
        date_to=request.date_to,
        session_id=request.session_id,
        images=request.images,
    )

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    # 토큰 사용량은 Langfuse 트레이스에서 확인한다 (이 로그에는 중복 기록하지 않음).
    # image_count를 남기는 이유: 게이트가 2줄(텍스트 10초 / 이미지 20초)이라
    # 로그만 보고 어느 기준으로 볼지 가릴 수 있어야 한다.
    logger.info(
        "request_id=%s report 요청 완료 model=%s elapsed_ms=%d unclassified_count=%d used_image=%s",
        request_id, get_model_name(), elapsed_ms, report.unclassified_count, report.used_image,
    )
    return report
