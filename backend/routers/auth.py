"""미등록 auth router. backend.main에 include_router 하기 전에는 endpoint가 노출되지 않는다."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.models.auth import LoginRequest, SignupRequest, TokenResponse, UserResponse
from backend.services.auth_db import AuthDatabase
from backend.services.auth_service import InvalidCredentialsError, create_access_token, decode_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=False)


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), database: AuthDatabase = Depends(AuthDatabase)) -> UserResponse:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="인증이 필요합니다.")
    try:
        user_id = decode_access_token(credentials.credentials)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    user = database.find_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="사용자를 찾을 수 없습니다.")
    return UserResponse(**user)


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(request: SignupRequest, database: AuthDatabase = Depends(AuthDatabase)) -> TokenResponse:
    email = request.email.strip().lower()
    if database.find_user_by_email(email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 가입된 이메일입니다.")
    user = UserResponse(**database.create_user(email, hash_password(request.password)))
    token, expires_in = create_access_token(user.user_id)
    return TokenResponse(access_token=token, expires_in=expires_in, user=user)


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, database: AuthDatabase = Depends(AuthDatabase)) -> TokenResponse:
    user = database.find_user_by_email(request.email.strip().lower())
    if user is None or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="이메일 또는 비밀번호가 올바르지 않습니다.")
    token, expires_in = create_access_token(user["user_id"])
    return TokenResponse(access_token=token, expires_in=expires_in, user=UserResponse(user_id=user["user_id"], email=user["email"], created_at=user["created_at"]))


@router.get("/me", response_model=UserResponse)
def me(user: UserResponse = Depends(get_current_user)) -> UserResponse:
    return user
