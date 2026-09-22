from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SignupRequest(BaseModel):
    email: str
    password: str = Field(min_length=12, max_length=256)


class LoginRequest(SignupRequest):
    pass


class UserResponse(BaseModel):
    user_id: str
    email: str
    created_at: datetime | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class HistoryCreateRequest(BaseModel):
    date_from: str | None = None
    date_to: str | None = None
    line_id: str | None = None
    equipment_id: str | None = None
    report_json: dict[str, Any]


class HistoryItemResponse(HistoryCreateRequest):
    history_id: str
    analyzed_at: datetime
