"""用户相关路由定义。"""

from fastapi import APIRouter, Depends

from app.api.v1.schemas.users import UserInfoResponse
from app.core.dependencies import get_current_active_user
from app.models.user import User
from app.services.user_service import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserInfoResponse)
def read_current_user(current_user: User = Depends(get_current_active_user)) -> UserInfoResponse:
    """返回当前已认证且激活用户的概要信息。"""
    return user_service.build_user_profile(current_user)
