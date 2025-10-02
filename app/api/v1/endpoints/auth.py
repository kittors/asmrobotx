"""认证相关路由定义。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    LogoutResponse,
)
from app.core.dependencies import get_db, get_current_active_user
from app.core.constants import HTTP_STATUS_OK
from app.core.responses import create_response
from app.services.auth_service import auth_service
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> RegisterResponse:
    """调用认证服务完成注册流程并返回统一响应。"""
    return auth_service.register_user(
        db,
        username=payload.username,
        password=payload.password,
        organization_id=payload.organization_id,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """校验凭证并签发访问令牌。"""
    return auth_service.login(db, username=payload.username, password=payload.password)


@router.post("/logout", response_model=LogoutResponse)
def logout(current_user: User = Depends(get_current_active_user)) -> LogoutResponse:
    """退出登录，前端需删除本地缓存的令牌。"""
    return create_response("退出登录成功", None, HTTP_STATUS_OK)
