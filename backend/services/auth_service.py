"""JWT와 password hashing 준비용 서비스. 실제 router 등록 전에는 호출되지 않는다."""

from datetime import UTC, datetime, timedelta
import os
from typing import Any


class AuthConfigurationError(RuntimeError):
    pass


class InvalidCredentialsError(ValueError):
    pass


def _bcrypt() -> Any:
    try:
        import bcrypt
    except ImportError as exc:
        raise AuthConfigurationError("bcrypt 패키지를 설치해야 password hashing을 사용할 수 있습니다.") from exc
    return bcrypt


def _jwt() -> Any:
    try:
        import jwt
    except ImportError as exc:
        raise AuthConfigurationError("PyJWT 패키지를 설치해야 JWT 인증을 사용할 수 있습니다.") from exc
    return jwt


def _secret() -> str:
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise AuthConfigurationError("JWT_SECRET 환경변수가 설정되지 않았습니다.")
    return secret


def _expires_seconds() -> int:
    return int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES_SECONDS", "3600"))


def hash_password(password: str) -> str:
    """bcrypt로 hash만 저장하며 plaintext를 반환하거나 저장하지 않는다."""
    return _bcrypt().hashpw(password.encode("utf-8"), _bcrypt().gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return _bcrypt().checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: str) -> tuple[str, int]:
    expires_in = _expires_seconds()
    now = datetime.now(UTC)
    token = _jwt().encode({"sub": user_id, "iat": now, "exp": now + timedelta(seconds=expires_in)}, _secret(), algorithm="HS256")
    return token, expires_in


def decode_access_token(token: str) -> str:
    try:
        payload = _jwt().decode(token, _secret(), algorithms=["HS256"])
        user_id = payload.get("sub")
    except Exception as exc:
        raise InvalidCredentialsError("유효하지 않거나 만료된 access token입니다.") from exc
    if not isinstance(user_id, str) or not user_id:
        raise InvalidCredentialsError("access token에 사용자 식별자가 없습니다.")
    return user_id
