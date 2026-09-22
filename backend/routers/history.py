"""미등록 history router. 사용자 ID는 요청에서 받지 않고 JWT에서만 결정한다."""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.models.auth import HistoryCreateRequest, HistoryItemResponse, UserResponse
from backend.routers.auth import get_current_user
from backend.services.history_service import HistoryService

router = APIRouter(prefix="/history", tags=["history"])


@router.post("", response_model=HistoryItemResponse, status_code=status.HTTP_201_CREATED)
def save_history(request: HistoryCreateRequest, user: UserResponse = Depends(get_current_user), service: HistoryService = Depends(HistoryService)) -> HistoryItemResponse:
    return HistoryItemResponse(**service.save_for_user(user.user_id, request))


@router.get("", response_model=list[HistoryItemResponse])
def list_history(user: UserResponse = Depends(get_current_user), service: HistoryService = Depends(HistoryService)) -> list[HistoryItemResponse]:
    return [HistoryItemResponse(**item) for item in service.list_for_user(user.user_id)]


@router.get("/{history_id}", response_model=HistoryItemResponse)
def get_history(history_id: str, user: UserResponse = Depends(get_current_user), service: HistoryService = Depends(HistoryService)) -> HistoryItemResponse:
    item = service.get_for_user(user.user_id, history_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="분석 기록을 찾을 수 없습니다.")
    return HistoryItemResponse(**item)
